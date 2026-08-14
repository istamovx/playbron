"""FastAPI dependency'lari — autentifikatsiya va rol tekshiruvi."""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.db import session_scope
from playbron.core.errors import Forbidden, Unauthorized
from playbron.core.http import client_ip
from playbron.core.security import AUDIENCE_STAFF, decode_access
from playbron.models import CLUB_ROLES, ROLE_ADMIN, ROLE_OWNER, ROLE_STAFF


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Authorization sarlavhasi yo‘q", code="NO_TOKEN")
    return authorization.split(" ", 1)[1].strip()


async def current_claims(
    authorization: Annotated[str | None, Header()] = None,
    x_club_id: Annotated[int | None, Header(alias="X-Club-Id")] = None,
) -> dict[str, Any]:
    """Tokenni ochadi va so'rov kontekstini to'ldiradi.

    `X-Club-Id` — faol klub. Foydalanuvchi o'sha klubda a'zo bo'lishi shart.
    """
    claims = decode_access(_bearer(authorization))
    audience = claims.get("aud")

    # Mijoz tokeni klub tanlay olmaydi: `X-Club-Id` xodim dunyosining sarlavhasi
    if x_club_id is not None and audience != AUDIENCE_STAFF:
        raise Forbidden("Bu amal uchun ruxsat yo‘q", code="STAFF_TOKEN_REQUIRED")

    memberships = claims.get("mbr") or []
    roles = {int(m["club_id"]): m["role"] for m in memberships}
    orgs = {int(m["club_id"]): m.get("org_id") for m in memberships}

    club_id: int | None = None
    if x_club_id is not None:
        if x_club_id not in roles:
            raise Forbidden("Bu klubga ruxsat yo‘q", code="CLUB_FORBIDDEN")
        club_id = x_club_id
    elif len(roles) == 1:
        club_id = next(iter(roles))

    ctx = context.RequestContext(
        request_id=context.current().request_id,
        user_id=int(claims["sub"]),
        club_id=club_id,
        # RLS `app.org_id` ga tayanadi — faol klub tanlanganda uning tashkiloti ham
        # kontekstga tushadi, aks holda xodim tashkilot yozuvini ko'ra olmaydi
        org_id=orgs.get(club_id) if club_id is not None else None,
        is_super_admin=bool(claims.get("sa")),
        roles=roles,
    )
    context.set_context(ctx)
    return claims


async def db(_: Annotated[dict[str, Any], Depends(current_claims)]) -> AsyncIterator[AsyncSession]:
    """RLS ostidagi sessiya — kontekst to'ldirilgandan keyin ochiladi."""
    async with session_scope() as session:
        yield session


async def public_db() -> AsyncIterator[AsyncSession]:
    """Token talab qilinmaydigan marshrutlar uchun (auth, public klublar)."""
    async with session_scope() as session:
        yield session


async def require_staff_token(
    claims: Annotated[dict[str, Any], Depends(current_claims)],
) -> None:
    """Token xodim dunyosiga tegishli bo'lishi shart.

    Tekshiruv `aud` klaymi bo'yicha, chunki uni `jwt.decode` ning o'zi
    majburlaydi (klaym yo'q bo'lsa token umuman ochilmaydi). Qo'lda
    `if knd == 'customer': deny` yozilsa, teskari yozilgan shart da'vosi
    YO'Q tokenni xodim deb qabul qilardi (§6.6).
    """
    if claims.get("aud") != AUDIENCE_STAFF:
        raise Forbidden("Bu amal uchun ruxsat yo‘q", code="STAFF_TOKEN_REQUIRED")


def require_role(*allowed: str):
    """Faol klubda kerakli roldan biri borligini talab qiladi.

    DIQQAT: super admin uchun ISTISNO YO'Q. Ilgari shu yerda
    `if ctx.is_super_admin: return` turardi — u auditsiz, muddatsiz va
    sababsiz impersonation yo'li edi va glass rejimi yonidan aylanib
    o'tadigan parallel kanal bo'lib qolardi (`docs/06-super-admin.md` §0.1,
    P0-2). Super admin klub ma'lumotiga faqat glass rejimi orqali kiradi,
    u esa muddat, sabab va audit bilan keladi.
    """
    unknown = set(allowed) - set(CLUB_ROLES)
    if unknown:
        raise ValueError(f"Noma'lum rol: {unknown}")

    async def guard(_: Annotated[None, Depends(require_staff_token)]) -> None:
        ctx = context.current()
        if ctx.club_id is None:
            raise Forbidden("Klub tanlanmagan", code="CLUB_REQUIRED")
        role = ctx.roles.get(ctx.club_id)
        if role not in allowed:
            raise Forbidden("Bu amal uchun ruxsat yo‘q", code="ROLE_FORBIDDEN")

    return guard


require_owner = require_role(ROLE_OWNER)
require_admin = require_role(ROLE_OWNER, ROLE_ADMIN)
require_staff = require_role(ROLE_OWNER, ROLE_ADMIN, ROLE_STAFF)


async def require_super_admin(
    request: Request,
    _: Annotated[None, Depends(require_staff_token)] = None,
) -> None:
    """Super admin qatlami.

    Panel borligi bilinmasligi uchun **404** qaytariladi, 403 emas.
    """
    from playbron.core.config import settings

    if not context.current().is_super_admin:
        raise Unauthorized("Topilmadi", code="NOT_FOUND", status_code=404)

    allowlist = settings.platform_ips
    if allowlist:
        # DIQQAT: `request.client.host` ishlatilmaydi — uvicorn
        # `--forwarded-allow-ips='*'` bilan yurganda u XFF'ning mijoz
        # boshqaradigan eng chap elementiga aylanadi va allowlist'ni ma'nosiz
        # qilardi. `client_ip()` LB o'zi qo'shadigan eng o'ng elementni oladi.
        ip = client_ip(request) or ""
        if ip not in allowlist:
            raise Unauthorized("Topilmadi", code="NOT_FOUND", status_code=404)
