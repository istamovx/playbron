"""`/api/v1/platform/...` — super admin, cross-tenant.

O'qish marshrutlari `platform_db` ga bog'liq (`deps.py`) — ichida
`require_super_admin` allaqachon bor. Klub/tashkilot yaratish (`POST
/platform/orgs`) esa ATAYLAB oddiy `db` (`playbron_app`) orqali —
`auth_owner_signup()` SECURITY DEFINER funksiyasi shu rolga ochiq
(`0008_owner_signup.py`), yangi yo'l ochilmaydi. To'lov yozuvi
(`platform_write_db`) — platforma-xos yozish, `0016_platform_org_admin.py`.
"""

from typing import Annotated, Any, Literal

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
    last_payment_amount: int | None
    last_payment_at: str | None
    plan_expires_at: str | None


@router.get("/orgs", response_model=list[OrgOut])
async def list_orgs(session: Annotated[AsyncSession, Depends(platform_db)]) -> list[OrgOut]:
    rows = await service.list_organizations(session)
    return [OrgOut(**row) for row in rows]


class OrgClubOut(BaseModel):
    club_id: int
    club_name: str
    club_status: str
    address: str
    phone: str | None
    stations_count: int
    bookings_30d: int


class OrgPaymentOut(BaseModel):
    id: int
    amount: int
    plan_code: str | None
    period_months: int | None
    paid_at: str
    note: str | None
    entered_by_name: str | None


class OrgStaffOut(BaseModel):
    user_id: int
    first_name: str
    login: str | None
    role: str
    club_id: int
    club_name: str


class OrgDetailOut(BaseModel):
    org_id: int
    org_name: str
    org_status: str
    plan_code: str | None
    created_at: str
    owner_name: str
    owner_login: str | None
    clubs: list[OrgClubOut]
    payments: list[OrgPaymentOut]
    staff: list[OrgStaffOut]


@router.get("/orgs/{org_id}", response_model=OrgDetailOut)
async def org_detail(
    org_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(platform_db)],
) -> OrgDetailOut:
    """"Ko'rish" (Preview) — klublar, TO'LIQ to'lov tarixi, xodimlar.
    `list_orgs` faqat oxirgi to'lovni ko'rsatadi, bu yerda hammasi (reja #17)."""
    row = await service.get_organization_detail(session, org_id=org_id)
    return OrgDetailOut(**row)


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


class OrgUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["pending", "active", "suspended"] | None = None


class OrgUpdateOut(BaseModel):
    org_id: int
    org_name: str
    org_status: str
    # `suspended` qilinganda yopilgan ochiq sessiyalar soni (`0030`).
    # Super admin amal HAQIQATAN kuchga kirganini ko'rsin.
    revoked_sessions: int = 0


@router.patch("/orgs/{org_id}", response_model=OrgUpdateOut)
async def update_org(
    body: OrgUpdateIn,
    org_id: Annotated[int, Path()],
    _: Annotated[None, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(platform_write_db)],
) -> OrgUpdateOut:
    """Nomi/holatini tahrirlash — `POST /orgs/{id}/payments` (`plan_code`)
    bilan bir vazifani bajarmasin, deb ATAYLAB alohida yo'l (audit
    topilmasi, 2026-08-16, reja #16)."""
    row = await service.update_organization(
        session, org_id=org_id, name=body.name, status=body.status
    )
    return OrgUpdateOut(**row)


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


class PlatformLogOut(BaseModel):
    id: str
    at: str
    action: str
    target: str | None
    org_id: int | None
    actor_name: str | None
    actor_login: str | None
    detail: dict[str, Any] | None


@router.get("/logs", response_model=list[PlatformLogOut])
async def platform_logs(
    session: Annotated[AsyncSession, Depends(platform_db)],
    limit: int = 100,
) -> list[PlatformLogOut]:
    rows = await service.list_platform_logs(session, limit=max(1, min(limit, 200)))
    return [PlatformLogOut(**row) for row in rows]


class BotStatusOut(BaseModel):
    """Bitta botning holati. TOKEN HECH QACHON QAYTARILMAYDI."""

    label: str
    configured: bool
    ok: bool
    username: str | None = None
    webhook_url: str | None = None
    pending_updates: int | None = None
    last_error: str | None = None
    problem: str | None = None


@router.get("/bots", response_model=list[BotStatusOut], dependencies=[Depends(require_super_admin)])
async def bot_status() -> list[BotStatusOut]:
    """Ikkala Telegram botining jonli holati.

    Loyiha egasining takroriy muammosi (2026-08-16/17): token noto'g'ri
    yoki webhook o'rnatilmagan bo'lsa ilova JIM qoladi — bot shunchaki
    javob bermaydi, hech qayerda xato ko'rinmaydi. Sababni topish uchun
    har safar tokenni qo'lda tekshirish kerak edi.

    Ikki narsa tekshiriladi:
      `getMe`          — token haqiqiymi (username ham shundan);
      `getWebhookInfo` — webhook aynan SHU API'ga qaratilganmi, navbatda
                         qancha yangilanish turibdi va Telegram oxirgi
                         marta nima xato bergan.

    MUHIM: webhook FAQAT API start'ida ro'yxatdan o'tadi (`main.py`
    lifespan). Ya'ni tokenni almashtirgach servis qayta ishga tushishi
    SHART, aks holda webhook eski botga qaragan bo'lib qolaveradi.
    """
    from playbron.core import telegram_api
    from playbron.core.config import settings

    expected_base = (settings.public_url or "").rstrip("/")
    checks = [
        ("Mijoz boti", settings.bot_token.get_secret_value(), "/api/v1/telegram/webhook/main"),
        (
            "Platforma boti",
            settings.admin_bot_token.get_secret_value(),
            "/api/v1/auth/telegram/webhook/admin",
        ),
    ]

    out: list[BotStatusOut] = []
    for label, token, path in checks:
        if not token:
            out.append(
                BotStatusOut(
                    label=label,
                    configured=False,
                    ok=False,
                    problem="Token sozlanmagan (Render → Environment)",
                )
            )
            continue

        me = await telegram_api.get_me(token)
        if me is None:
            out.append(
                BotStatusOut(
                    label=label,
                    configured=True,
                    ok=False,
                    problem="Token Telegram tomonidan rad etildi — @BotFather'dan yangisini oling",
                )
            )
            continue

        info = await telegram_api.call(token, "getWebhookInfo", {})
        webhook_url = (info or {}).get("url") or None
        expected = f"{expected_base}{path}" if expected_base else None

        problem: str | None = None
        if not webhook_url:
            problem = "Webhook o‘rnatilmagan — API'ni qayta ishga tushiring"
        elif expected and webhook_url != expected:
            problem = f"Webhook boshqa manzilga qaragan: {webhook_url}"

        out.append(
            BotStatusOut(
                label=label,
                configured=True,
                ok=problem is None,
                username=me.get("username"),
                webhook_url=webhook_url,
                pending_updates=(info or {}).get("pending_update_count"),
                last_error=(info or {}).get("last_error_message"),
                problem=problem,
            )
        )

    # ── Ikkala yuza BITTA botga qaragan holati ────────────────────────────
    # Eng ziyonli va eng qiyin sezinadigan nosozlik. `main.py` lifespan
    # ikkala webhook'ni KETMA-KET ro'yxatdan o'tkazadi; bitta bot ikkala
    # yuzaga ishlatilsa ikkinchi `setWebhook` birinchisini BOSIB KETADI.
    # Natijada bitta bot butunlay jim qoladi — Telegram xato bermaydi,
    # log'da ham hech nima yo'q.
    #
    # `ADMIN_BOT_TOKEN` umuman berilmasa ham shu holat yuzaga keladi:
    # `_admin_token()` `BOT_TOKEN` ga tushadi (`botlogin.py`).
    live = [row for row in out if row.username]
    if len(live) == 2 and live[0].username == live[1].username:
        for row in live:
            row.ok = False
            row.problem = (
                f"Ikkala yuza ham BITTA botga (@{row.username}) qaragan — "
                "webhook'lar bir-birini bosib ketadi va bitta bot jim qoladi. "
                "BOT_TOKEN va ADMIN_BOT_TOKEN HAR XIL bot bo'lishi shart."
            )

    return out
