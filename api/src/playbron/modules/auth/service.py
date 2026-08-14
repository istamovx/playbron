"""Auth servisi — ikkala Telegram kanali uchun yagona natija."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.config import settings
from playbron.core.db import (
    AppSession,
    set_current_user,
    set_refresh_scope,
    set_telegram_scope,
)
from playbron.core.errors import Unauthorized
from playbron.core.redis import redis_client
from playbron.core.security import (
    encode_access,
    new_refresh_token,
    now,
    sha256_hex,
)
from playbron.core.text import clean_name, clean_username
from playbron.models import Club, Membership, Organization, Plan, RefreshToken, SuperAdmin, User
from playbron.modules.auth.telegram import TelegramIdentity

REPLAY_PREFIX = "auth:used:"


async def guard_replay(identity: TelegramIdentity) -> None:
    """Bir imzo ikki marta ishlatilmasin.

    Redis'da `SET NX` — birinchi kelgan o'tadi, ikkinchisi rad etiladi.
    TTL imzo yashash muddatiga teng, ya'ni eskirgani o'zi tozalanadi.
    """
    ttl = (
        settings.initdata_ttl_sec
        if identity.source == "initdata"
        else settings.widget_ttl_sec
    )
    key = f"{REPLAY_PREFIX}{identity.source}:{identity.raw_hash}"

    stored = await redis_client().set(key, "1", ex=ttl, nx=True)
    if not stored:
        raise Unauthorized("Imzo allaqachon ishlatilgan", code="AUTH_REPLAY")


async def upsert_user(session: AsyncSession, identity: TelegramIdentity) -> User:
    """Telegram profili bo'yicha foydalanuvchini yaratadi yoki yangilaydi.

    Telefon **tegilmaydi** — u faqat `requestContact` orqali to'ladi.
    """
    # Bu maydonlarni foydalanuvchi to'liq nazorat qiladi (Telegram profili) —
    # tozalash aynan yozish nuqtasida (§3.8)
    first_name = clean_name(identity.first_name)
    last_name = clean_name(identity.last_name) or None
    username = clean_username(identity.username)

    stmt = (
        insert(User)
        .values(
            kind="customer",
            telegram_id=identity.telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=identity.language_code,
            photo_url=identity.photo_url,
            last_seen_at=now(),
        )
        .on_conflict_do_update(
            # `telegram_id` UNIQUE indeksi endi QISMAN (`WHERE kind='customer'`),
            # shuning uchun `index_where` siz Postgres uni topolmaydi:
            # «there is no unique or exclusion constraint matching the
            # ON CONFLICT specification».
            index_elements=[User.telegram_id],
            index_where=User.kind == "customer",
            set_={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": identity.language_code,
                "photo_url": identity.photo_url,
                "last_seen_at": now(),
            },
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def is_super_admin(session: AsyncSession, user_id: int) -> bool:
    found = await session.scalar(select(SuperAdmin.user_id).where(SuperAdmin.user_id == user_id))
    return found is not None


async def load_memberships(session: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    """Foydalanuvchining barcha klublardagi rollari."""
    rows = await session.execute(
        select(Membership.club_id, Membership.role, Club.name, Club.org_id)
        .join(Club, Club.id == Membership.club_id)
        .where(Membership.user_id == user_id, Membership.status == "active")
        .order_by(Club.name)
    )
    return [
        {"club_id": club_id, "role": role, "club_name": club_name, "org_id": org_id}
        for club_id, role, club_name, org_id in rows.all()
    ]


async def load_entitlements(session: AsyncSession, org_id: int | None) -> dict[str, Any]:
    """Tarif limitlari va funksiyalari.

    Faza 1: manba — `organizations.plan_code`.
    Faza 5: `subscriptions` jadvali manba bo'ladi, bu funksiya o'sha yerga qaraydi.
    """
    if org_id is None:
        return {"plan": None, "limits": {}, "features": []}

    row = await session.execute(
        select(Plan.code, Plan.limits, Plan.features)
        .join(Organization, Organization.plan_code == Plan.code)
        .where(Organization.id == org_id)
    )
    found = row.first()
    if not found:
        return {"plan": None, "limits": {}, "features": []}

    code, limits, features = found
    return {"plan": code, "limits": limits or {}, "features": features or []}


async def issue_tokens(
    session: AsyncSession,
    *,
    user: User,
    memberships: list[dict[str, Any]],
    super_admin: bool,
    entitlements: dict[str, Any] | None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    access, access_exp = encode_access(
        user_id=user.id,
        # `org_id` ham tokenga kiradi: RLS `app.org_id` ga tayanadi va usiz
        # xodim o'z klubining tashkilotini (demak tarifini) ko'ra olmaydi
        memberships=[
            {"club_id": m["club_id"], "role": m["role"], "org_id": m["org_id"]}
            for m in memberships
        ],
        is_super_admin=super_admin,
        entitlements=entitlements,
    )

    refresh = new_refresh_token()
    ttl = settings.sa_refresh_ttl_sec if super_admin else settings.refresh_ttl_sec
    expires_at = now() + timedelta(seconds=ttl)

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256_hex(refresh),
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
    )

    return {
        "access_token": access,
        "access_expires_at": access_exp,
        "refresh_token": refresh,
        "refresh_expires_at": expires_at,
    }


async def revoke_all_tokens(user_id: int) -> int:
    """Foydalanuvchining barcha faol refresh tokenlarini bekor qiladi.

    O'z tranzaksiyasini ochadi: chaqiruvchi odatda darhol xato tashlaydi va
    asosiy tranzaksiya qaytariladi — bekor qilish esa saqlanib qolishi shart.
    `app.user_id` shu yerda o'rnatiladi, aks holda RLS policy yozishga yo'l bermaydi.
    """
    async with AppSession() as session:
        async with session.begin():
            await set_current_user(session, user_id)
            result = await session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now())
            )
    return int(result.rowcount or 0)


async def rotate_refresh(
    session: AsyncSession,
    *,
    presented: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Refresh tokenni almashtiradi.

    Ishlatilgan token qayta kelsa — o'g'irlangan deb hisoblanadi va shu
    foydalanuvchining barcha tokenlari bekor qilinadi.
    """
    token_hash = sha256_hex(presented)

    # RLS: hali kim ekanimiz noma'lum — policy'ga aynan shu xeshli qator ochiladi
    await set_refresh_scope(session, token_hash)

    # `FOR UPDATE` — bir vaqtda kelgan ikkita refresh so'rovi navbatga tushadi.
    # Qulfsiz holatda ikkalasi ham "bekor qilinmagan" deb ko'rib, bitta tokendan
    # ikkita amal qiluvchi sessiya yasab yuborardi.
    row = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )
    stored = row.scalar_one_or_none()

    if stored is None:
        raise Unauthorized("Refresh token topilmadi", code="REFRESH_INVALID")

    if stored.revoked_at is not None:
        # Bekor qilingan token qayta ishlatildi — o'g'irlangan deb hisoblaymiz.
        # Bekor qilish **alohida tranzaksiyada**: quyidagi `raise` joriy
        # tranzaksiyani qaytaradi va aks holda bekor qilish yo'qolib ketardi.
        await revoke_all_tokens(stored.user_id)
        raise Unauthorized("Token qayta ishlatilgan", code="REFRESH_REUSED")

    if stored.expires_at <= datetime.now(UTC):
        raise Unauthorized("Refresh muddati tugagan", code="REFRESH_EXPIRED")

    # Refresh so'rovida token hali yo'q — kontekst shu yerda o'rnatiladi
    await set_current_user(session, stored.user_id)

    user = await session.get(User, stored.user_id)
    if user is None:
        raise Unauthorized("Foydalanuvchi topilmadi", code="USER_NOT_FOUND")

    super_admin = await is_super_admin(session, user.id)
    memberships = await load_memberships(session, user.id)
    org_id = memberships[0]["org_id"] if memberships else None
    entitlements = await load_entitlements(session, org_id)

    issued = await issue_tokens(
        session,
        user=user,
        memberships=memberships,
        super_admin=super_admin,
        entitlements=entitlements,
        user_agent=user_agent,
        ip=ip,
    )

    stored.revoked_at = now()
    stored.replaced_by = sha256_hex(issued["refresh_token"])

    return {**issued, "user": user, "memberships": memberships, "is_super_admin": super_admin}


async def sign_in(
    session: AsyncSession,
    identity: TelegramIdentity,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Imzosi tekshirilgan identity → sessiya."""
    await guard_replay(identity)

    # RLS: foydalanuvchi hali yo'q, shuning uchun policy'ga aynan shu telegram_id ochiladi
    await set_telegram_scope(session, identity.telegram_id)
    user = await upsert_user(session, identity)

    # `SET LOCAL` ni yangilaymiz — Python kontekstini o'zgartirish DB'ga ta'sir qilmaydi,
    # keyingi yozuvlar (refresh_tokens) esa `app.user_id` ga tayanadi
    await set_current_user(session, user.id)
    ctx = context.current()
    ctx.user_id = user.id
    ctx.telegram_id = identity.telegram_id
    context.set_context(ctx)

    super_admin = await is_super_admin(session, user.id)
    memberships = await load_memberships(session, user.id)
    org_id = memberships[0]["org_id"] if memberships else None
    entitlements = await load_entitlements(session, org_id)

    issued = await issue_tokens(
        session,
        user=user,
        memberships=memberships,
        super_admin=super_admin,
        entitlements=entitlements,
        user_agent=user_agent,
        ip=ip,
    )

    return {**issued, "user": user, "memberships": memberships, "is_super_admin": super_admin}


async def sign_out(session: AsyncSession, *, refresh_token: str) -> None:
    """Chiqish — token bekor qilinadi.

    RLS: `WITH CHECK (user_id = app_user_id())` shart, shuning uchun marshrut
    autentifikatsiyadan keyingi sessiyani beradi (`deps.db`), `app.user_id` to'ldirilgan.
    """
    token_hash = sha256_hex(refresh_token)
    await set_refresh_scope(session, token_hash)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now())
    )
