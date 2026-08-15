"""`/api/v1/platform/...` — super admin, cross-tenant o'qish.

Har bir marshrut `platform_db` ga bog'liq (`deps.py`) — u ichida
`require_super_admin` allaqachon bor, shuning uchun bu yerda qo'shimcha
tekshiruv shart emas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.deps import platform_db
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
