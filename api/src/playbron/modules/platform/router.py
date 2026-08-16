"""`/api/v1/platform/...` — super admin, cross-tenant.

O'qish marshrutlari `platform_db` ga bog'liq (`deps.py`) — ichida
`require_super_admin` allaqachon bor. Klub/tashkilot yaratish (`POST
/platform/orgs`) esa ATAYLAB oddiy `db` (`playbron_app`) orqali —
`auth_owner_signup()` SECURITY DEFINER funksiyasi shu rolga ochiq
(`0008_owner_signup.py`), yangi yo'l ochilmaydi. To'lov yozuvi
(`platform_write_db`) — platforma-xos yozish, `0016_platform_org_admin.py`.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.deps import db, platform_db, platform_write_db, require_super_admin
from playbron.modules.platform import service

router = APIRouter(prefix="/platform", tags=["platform"])


class TopClubOut(BaseModel):
    club_id: int
    club_name: str
    org_name: str
    bookings: int


class DashboardOut(BaseModel):
    organizations_total: int
    clubs_active: int
    clubs_draft: int
    bookings_today: int
    revenue_today: int
    bookings_this_month: int
    revenue_this_month: int
    daily_trend: dict[str, int]
    top_clubs: list[TopClubOut]


@router.get("/stats", response_model=DashboardOut)
async def dashboard(session: Annotated[AsyncSession, Depends(platform_db)]) -> DashboardOut:
    data = await service.get_dashboard(session)
    return DashboardOut(**data)


class OrgOut(BaseModel):
    org_id: int
    org_name: str
    org_status: str
    plan_code: str | None
    created_at: str
    owner_name: str
    owner_login: str | None
    club_id: int | None
    club_name: str | None
    club_status: str | None
    stations_count: int
    bookings_30d: int


@router.get("/orgs", response_model=list[OrgOut])
async def list_orgs(session: Annotated[AsyncSession, Depends(platform_db)]) -> list[OrgOut]:
    rows = await service.list_organizations(session)
    return [OrgOut(**row) for row in rows]


class OrgCreateIn(BaseModel):
    """`auth/router.py::OwnerSignupIn` bilan ATAYLAB bir xil maydonlar —
    `signup.owner_signup()`ning o'zi ishlatiladi (`service.py`)."""

    first_name: str = Field(min_length=1, max_length=128)
    club_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    address: str = Field(min_length=1, max_length=600)
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class OrgCreateOut(BaseModel):
    login: str


@router.post("/orgs", response_model=OrgCreateOut, status_code=201)
async def create_org(
    body: OrgCreateIn,
    request: Request,
    _: Annotated[None, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(db)],
) -> OrgCreateOut:
    """Klubni qo'lda qo'shish — to'lov tizimida muammo bo'lganda yoki
    mijoz o'zi ro'yxatdan o'tolmaganda (§ so'rov, 2026-08-16)."""
    actor_user_id = context.current().user_id
    login = await service.create_manual_org(
        session, body=body.model_dump(), request=request, actor_user_id=actor_user_id
    )
    return OrgCreateOut(login=login)


class PaymentIn(BaseModel):
    amount: int = Field(gt=0)
    plan_code: str | None = Field(default=None, max_length=32)
    period_months: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class PaymentOut(BaseModel):
    id: int
    org_id: int
    amount: int
    plan_code: str | None
    period_months: int | None
    paid_at: str
    note: str | None


@router.post("/orgs/{org_id}/payments", response_model=PaymentOut, status_code=201)
async def create_payment(
    body: PaymentIn,
    org_id: Annotated[int, Path()],
    _: Annotated[None, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(platform_write_db)],
) -> PaymentOut:
    actor_user_id = context.current().user_id
    row = await service.record_payment(
        session,
        org_id=org_id,
        amount=body.amount,
        plan_code=body.plan_code,
        period_months=body.period_months,
        note=body.note,
        entered_by=actor_user_id,
    )
    return PaymentOut(**row)


class FinancialReportOut(BaseModel):
    period: str
    revenue_by_bucket: dict[str, int]
    new_orgs_by_bucket: dict[str, int]
    total_revenue: int
    total_organizations: int


@router.get("/report", response_model=FinancialReportOut)
async def financial_report(
    session: Annotated[AsyncSession, Depends(platform_db)],
    period: Literal["day", "week", "month", "year"] = "month",
) -> FinancialReportOut:
    data = await service.get_financial_report(session, period=period)
    return FinancialReportOut(**data)
