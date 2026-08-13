"""`/api/v1/me` — joriy foydalanuvchi va uning huquqlari."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import NotFound
from playbron.deps import current_claims, db
from playbron.models import Club, Membership, User
from playbron.modules.auth.service import load_entitlements

router = APIRouter(tags=["me"])


class ClubBrief(BaseModel):
    id: int
    name: str
    role: str
    org_id: int
    status: str


class MeOut(BaseModel):
    id: int
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    phone: str | None
    phone_verified: bool
    is_super_admin: bool
    clubs: list[ClubBrief]


class EntitlementsOut(BaseModel):
    plan: str | None
    limits: dict[str, Any]
    features: list[str]


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

    return MeOut(
        id=user.id,
        telegram_id=user.telegram_id,
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
