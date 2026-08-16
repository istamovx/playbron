"""Ulanish va tenant konteksti.

Ikkita alohida pool:
  • `app_engine`      — `playbron_app` roli, RLS ostida. Barcha oddiy so'rovlar.
  • `platform_engine` — `playbron_platform` roli, BYPASSRLS. Faqat `/platform/*`.

RLS policy'lari `current_setting('app.*')` ni o'qiydi, shuning uchun har bir tranzaksiya
boshida `SET LOCAL` qilinadi. `SET LOCAL` tranzaksiya tugashi bilan o'zi bekor bo'ladi —
pool'dagi ulanish keyingi so'rovga «iflos» holda o'tmaydi.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from playbron.core import context
from playbron.core.config import settings


class Base(DeclarativeBase):
    pass


app_engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=settings.debug,
)

platform_engine: AsyncEngine = create_async_engine(
    settings.platform_database_url,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
    echo=settings.debug,
)

AppSession = async_sessionmaker(app_engine, expire_on_commit=False)
PlatformSession = async_sessionmaker(platform_engine, expire_on_commit=False)


async def _apply_context(session: AsyncSession) -> None:
    """Joriy so'rov kontekstini `SET LOCAL app.*` ga yozadi.

    `set_config(..., true)` — `true` = local, ya'ni tranzaksiya doirasida.
    Parametrlar bind qilinadi, satr birlashtirish yo'q (SQL injection'dan himoya).
    """
    ctx = context.current()
    await session.execute(
        text(
            "SELECT set_config('app.user_id', :user_id, true),"
            "       set_config('app.org_id', :org_id, true),"
            "       set_config('app.club_id', :club_id, true),"
            "       set_config('app.club_role', :club_role, true),"
            "       set_config('app.telegram_id', :telegram_id, true),"
            "       set_config('app.is_super_admin', :sa, true)"
        ),
        {
            "user_id": str(ctx.user_id or 0),
            "org_id": str(ctx.org_id or 0),
            "club_id": str(ctx.club_id or 0),
            # `memberships` policy'lari rolni SHU YERDAN oladi, jadvaldan emas:
            # jadvaldan o'qish o'sha jadval policy'sini qayta ishga solib
            # cheksiz rekursiya berardi (`0007` migratsiyasiga qara).
            # Qiymat imzolangan tokendagi a'zolikdan keladi va faol klub
            # `current_claims` da a'zolik ro'yxatiga qarab tekshiriladi.
            "club_role": (ctx.roles.get(ctx.club_id) or "") if ctx.club_id else "",
            "telegram_id": str(ctx.telegram_id or 0),
            "sa": "true" if ctx.is_super_admin else "false",
        },
    )


async def set_current_user(session: AsyncSession, user_id: int) -> None:
    """Tranzaksiya o'rtasida `app.user_id` ni yangilaydi.

    Kirish oqimida foydalanuvchi tranzaksiya boshlanganidan **keyin** yaratiladi;
    Python kontekstini o'zgartirish DB sozlamasini yangilamaydi, shuning uchun
    `set_config` qayta chaqiriladi — aks holda keyingi yozuvlar RLS ostida rad etiladi.
    """
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def set_telegram_scope(session: AsyncSession, telegram_id: int) -> None:
    """Kirish tranzaksiyasi uchun `users` dagi bitta qatorni ochadi."""
    await session.execute(
        text("SELECT set_config('app.telegram_id', :telegram_id, true)"),
        {"telegram_id": str(telegram_id)},
    )


async def set_refresh_scope(session: AsyncSession, token_hash: str) -> None:
    """Refresh almashtirishda `refresh_tokens` dagi bitta qatorni ochadi.

    Token — 48 baytli tasodifiy sir; uning xeshini bilish o'zi huquq beradi,
    shuning uchun policy aynan shu xeshli qatorga ruxsat beradi, boshqasiga emas.
    """
    await session.execute(
        text("SELECT set_config('app.refresh_hash', :token_hash, true)"),
        {"token_hash": token_hash},
    )


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """RLS ostidagi sessiya. Kontekst tranzaksiya ichida o'rnatiladi."""
    async with AppSession() as session:
        async with session.begin():
            await _apply_context(session)
            yield session


@asynccontextmanager
async def platform_scope() -> AsyncIterator[AsyncSession]:
    """Cross-tenant o'qish. Faqat super admin marshrutlari uchun.

    `playbron_platform` **haqiqiy** BYPASSRLS bo'lsa bu pool RLS'ni butunlay
    chetlab o'tadi. Lekin Render bepul rejasida rol BYPASSRLS ololmaydi
    (`0001_core.py::_create_roles()` buni jimgina yutadi —
    `[[render-free-tier-no-bypassrls]]`), ya'ni faqat shu sabab bilan
    ishlashga tayanish prod'da statistikani doim bo'sh qaytarardi. Shu
    yerda ham `SET LOCAL app.platform` qo'yiladi — `0015_platform_stats.py`
    dagi `*_platform_read` policy'lari orqali BYPASSRLS'siz muhitda ham
    ishlaydi (ikkalasi bir-birini yopadi, bittasi yetarli bo'lsa ham).

    Bu pool RLS'ni chetlab o'tadi, shuning uchun chaqiruvchi **oldindan**
    super admin ekanini tekshirgan bo'lishi shart.
    """
    if not context.current().is_super_admin:
        raise PermissionError("platform_scope faqat super admin uchun")

    async with PlatformSession() as session:
        async with session.begin():
            # Faqat o'qish — bu pool yozish uchun emas, xato bilan yozib
            # yuborilsa ham DB darajasida to'xtaydi.
            await session.execute(text("SET TRANSACTION READ ONLY"))
            await session.execute(text("SELECT set_config('app.platform', 'true', true)"))
            yield session


@asynccontextmanager
async def platform_write_scope() -> AsyncIterator[AsyncSession]:
    """Platforma-XOS yozish — masalan qo'lda kiritilgan to'lov yozuvi.

    `platform_scope()`dan farqi: bu YOZISH uchun (`SET TRANSACTION READ
    ONLY` yo'q). Doirasi ataylab TOR — faqat `app_platform()` bilan
    qo'riqlanadigan jadvallarga (`platform_payments`) mo'ljallangan.
    Umumiy tenant jadvallariga (klub, tashkilot, xodim) yozish BU YERDAN
    EMAS — ular uchun `auth_owner_signup()` SECURITY DEFINER funksiyasi
    bor, u `playbron_app` orqali, `app.signup_login` GUC'i bilan ishlaydi
    (`0008_owner_signup.py`) — mavjud, tekshirilgan yo'l qayta ochilmaydi.
    """
    if not context.current().is_super_admin:
        raise PermissionError("platform_write_scope faqat super admin uchun")

    async with PlatformSession() as session:
        async with session.begin():
            await session.execute(text("SELECT set_config('app.platform', 'true', true)"))
            yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    async with session_scope() as session:
        yield session


async def ping() -> bool:
    async with app_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def dispose() -> None:
    await app_engine.dispose()
    await platform_engine.dispose()
