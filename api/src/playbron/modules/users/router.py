"""`/api/v1/me` — joriy foydalanuvchi va uning huquqlari."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import NotFound
from playbron.deps import current_claims, db, require_customer_token
from playbron.models import Club, Membership, User
from playbron.modules.auth.service import load_entitlements
from playbron.modules.bookings import service as bookings_service

router = APIRouter(tags=["me"])


class ClubBrief(BaseModel):
    id: int
    name: str
    role: str
    org_id: int
    status: str


class MeOut(BaseModel):
    id: int
    # Xodimda YO'Q: uning Telegrami shaxsni tasdiqlamaydi va alohida
    # `staff_telegram` jadvalida turadi (docs/05-auth-redesign.md §3.2)
    telegram_id: int | None
    login: str | None = None
    first_name: str
    last_name: str | None
    username: str | None
    phone: str | None
    phone_verified: bool
    is_super_admin: bool
    clubs: list[ClubBrief]
    # Xodim Telegram boti ulanganmi (`staff_telegram` yozuvi bor va
    # bloklanmagan). Loyiha egasining topilmasi (2026-08-16): "Telegram
    # ulanganda 'ulandi' ko'rsatadi, log out qilib qayta kirganda status
    # yo'q" — holat FAQAT `TelegramLinkPanel`ning lokal state'ida edi,
    # server hech qachon so'ralmasdi. Endi sessiya bilan birga keladi.
    telegram_linked: bool = False


class EntitlementsOut(BaseModel):
    plan: str | None
    limits: dict[str, Any]
    features: list[str]


class MyBookingOut(BaseModel):
    id: int
    status: str
    hours: int
    rate_snapshot: int
    starts_at: str
    ends_at: str
    station_code: str
    club_name: str


@router.get("/me", response_model=MeOut)
async def me(
    session: Annotated[AsyncSession, Depends(db)],
    _: Annotated[dict[str, Any], Depends(current_claims)] = None,  # type: ignore[assignment]
) -> MeOut:
    ctx = context.current()
    user = await session.get(User, ctx.user_id)
    if user is None:
        raise NotFound("Foydalanuvchi topilmadi")

    rows = await session.execute(
        select(Club.id, Club.name, Club.org_id, Club.status, Membership.role)
        .join(Membership, Membership.club_id == Club.id)
        .where(Membership.user_id == user.id, Membership.status == "active")
        .order_by(Club.name)
    )

    # `staff_telegram_self` policy (`0010_staff_telegram_link.py`) aynan
    # shu qatorni ochadi (`user_id = app_user_id()`) — qo'shimcha GUC
    # yoki migratsiya kerak emas.
    linked = await session.scalar(
        text(
            "SELECT 1 FROM staff_telegram"
            " WHERE user_id = :uid AND blocked_at IS NULL"
        ),
        {"uid": user.id},
    )

    return MeOut(
        id=user.id,
        telegram_id=user.telegram_id,
        login=user.login,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        phone=user.phone,
        phone_verified=user.phone_verified_at is not None,
        is_super_admin=ctx.is_super_admin,
        clubs=[
            ClubBrief(id=cid, name=name, org_id=org_id, status=status, role=role)
            for cid, name, org_id, status, role in rows.all()
        ],
        telegram_linked=linked is not None,
    )


@router.get("/me/entitlements", response_model=EntitlementsOut)
async def entitlements(
    session: Annotated[AsyncSession, Depends(db)],
    _: Annotated[dict[str, Any], Depends(current_claims)] = None,  # type: ignore[assignment]
) -> EntitlementsOut:
    """Tarif limitlari va funksiyalari.

    Frontend bundan **faqat ko'rinish** uchun foydalanadi — haqiqiy to'siq backendda.
    """
    ctx = context.current()

    org_id: int | None = None
    if ctx.club_id is not None:
        org_id = await session.scalar(select(Club.org_id).where(Club.id == ctx.club_id))

    data = await load_entitlements(session, org_id)
    return EntitlementsOut(**data)


@router.get("/me/bookings", response_model=list[MyBookingOut])
async def my_bookings(
    session: Annotated[AsyncSession, Depends(db)],
    _: Annotated[None, Depends(require_customer_token)],
) -> list[MyBookingOut]:
    rows = await bookings_service.list_customer_bookings(session, context.current().user_id)
    return [MyBookingOut(**r) for r in rows]
