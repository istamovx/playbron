"""`SUPER_ADMIN_PASSWORD` orqali super admin paroli.

Manba: `docs/05-auth-redesign.md` §5.6 dagi chetlanish (2026-08-15).
Standart YO'L emas — loyiha egasining aniq so'rovi bilan qo'shilgan.
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from conftest import rls_bypass
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.core.passwords import hash_password, verify_password
from playbron.core.super_admin_bootstrap import sync_super_admin_password

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL kerak",
)

LOGIN = "sab.sinov"
PASSWORD = "Bootstrap Sinov Paroli 2026"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture
async def account() -> AsyncIterator[int]:
    """Super admin — parolsiz, boshlang'ich holatda."""
    engine = _owner_engine()
    async with engine.begin() as conn:
        # `account` butun grafni nol'dan quradi — hali tabiiy aktor yo'q
        # (`super_admins`da umuman INSERT policy'si yo'q), shuning uchun
        # `rls_bypass` (`conftest.py`).
        async with rls_bypass(conn, "users", "super_admins", "staff_credentials"):
            user_id = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'Sinov')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": LOGIN},
            )
            await conn.execute(
                text("INSERT INTO super_admins (user_id) VALUES (:uid) ON CONFLICT DO NOTHING"),
                {"uid": user_id},
            )
            await conn.execute(
                text("DELETE FROM staff_credentials WHERE user_id = :uid"), {"uid": user_id}
            )

    yield user_id

    async with engine.begin() as conn:
        async with rls_bypass(conn, "super_admins", "users"):
            await conn.execute(
                text("DELETE FROM super_admins WHERE user_id = :uid"), {"uid": user_id}
            )
            await conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def restore_settings() -> AsyncIterator[None]:
    """Sinovlararo `settings` global holatini tozalaydi."""
    original_password = settings.super_admin_password
    original_logins = settings.super_admin_logins
    yield
    settings.super_admin_password = original_password
    settings.super_admin_logins = original_logins


@skip_no_db
async def test_empty_password_is_a_noop() -> None:
    settings.super_admin_password = SecretStr("")
    settings.super_admin_logins = LOGIN
    # Xato chiqarmasligi yetarli — DB'ga tegilmaganini alohida tekshirmaymiz,
    # chunki funksiya birinchi qatorda qaytadi (kodga qarab isbotlangan).
    await sync_super_admin_password()


@skip_no_db
async def test_sets_password_for_configured_login(account: int) -> None:
    settings.super_admin_logins = LOGIN
    settings.super_admin_password = SecretStr(PASSWORD)

    await sync_super_admin_password()

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "staff_credentials"):
            row = await conn.execute(
                text(
                    "SELECT password_hash, must_change FROM staff_credentials WHERE user_id = :uid"
                ),
                {"uid": account},
            )
            password_hash, must_change = row.one()
    await engine.dispose()

    assert await verify_password(password_hash, PASSWORD)
    # O'zi tanlagan emas, lekin bootstrap orqali — darhol ishlaydigan bo'lishi
    # kerak, aks holda avtomatlashtirilgan sozlash foydasiz bo'lardi
    assert must_change is False


@skip_no_db
async def test_unchanged_password_does_not_revoke_sessions(account: int) -> None:
    """Ikkinchi marta bir xil parol bilan chaqirilsa — sessiyalar OMON qoladi.

    Aks holda har start/deploy'da super admin chiqarib yuborilardi.
    """
    settings.super_admin_logins = LOGIN
    settings.super_admin_password = SecretStr(PASSWORD)

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "staff_credentials", "refresh_tokens"):
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :hash, false)"
                ),
                {"uid": account, "hash": await hash_password(PASSWORD)},
            )
            await conn.execute(
                text(
                    "INSERT INTO refresh_tokens"
                    " (user_id, token_hash, kind, chain_started_at, expires_at)"
                    " VALUES (:uid, 'probe-hash-sab', 'staff', now(), now() + interval '1 day')"
                ),
                {"uid": account},
            )

    await sync_super_admin_password()

    async with engine.begin() as conn:
        async with rls_bypass(conn, "refresh_tokens"):
            revoked = await conn.scalar(
                text(
                    "SELECT revoked_at FROM refresh_tokens"
                    " WHERE user_id = :uid AND token_hash = 'probe-hash-sab'"
                ),
                {"uid": account},
            )
    await engine.dispose()

    assert revoked is None


@skip_no_db
async def test_changed_password_revokes_old_sessions(account: int) -> None:
    settings.super_admin_logins = LOGIN
    settings.super_admin_password = SecretStr(PASSWORD)

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "staff_credentials", "refresh_tokens"):
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :hash, false)"
                ),
                {"uid": account, "hash": await hash_password("boshqa mustahkam parol")},
            )
            await conn.execute(
                text(
                    "INSERT INTO refresh_tokens"
                    " (user_id, token_hash, kind, chain_started_at, expires_at)"
                    " VALUES (:uid, 'probe-hash-sab2', 'staff', now(), now() + interval '1 day')"
                ),
                {"uid": account},
            )

    await sync_super_admin_password()

    async with engine.begin() as conn:
        async with rls_bypass(conn, "refresh_tokens"):
            revoked = await conn.scalar(
                text(
                    "SELECT revoked_at FROM refresh_tokens"
                    " WHERE user_id = :uid AND token_hash = 'probe-hash-sab2'"
                ),
                {"uid": account},
            )
    await engine.dispose()

    assert revoked is not None


@skip_no_db
async def test_unknown_login_creates_a_new_super_admin(account: int) -> None:
    """Mavjud bo'lmagan login — hisob YARATILADI, o'tkazib yuborilmaydi.

    Test avval `test_unknown_login_is_skipped_without_error` deb atalgan
    va faqat "xato chiqmasin" deb tekshirardi — ya'ni nomi ham, izohi ham
    HAQIQIY xatti-harakatga ZID edi (`_sync_one()` login topilmasa
    `_create_super_admin_account()` chaqiradi). Xavfsizlikka daxldor
    yo'lda bunday nomlanish kod o'quvchisini chalg'itadi.

    Bu ATAYLAB shunday: birinchi deployda super admin hisobi shu yo'l
    bilan paydo bo'ladi (`render.yaml` izohi — bepul rejada Shell yo'q,
    qo'lda seed qilib bo'lmaydi). Shuning uchun test endi shu haqiqatni
    QULFLAYDI va o'zidan keyin tozalaydi (avval hisob bazada qolib
    ketardi — loyiha egasining dev bazasida shu tarzda yig'ilgan edi).
    """
    login = "yoq.bunday.login"
    settings.super_admin_logins = login
    settings.super_admin_password = SecretStr(PASSWORD)

    engine = _owner_engine()
    try:
        await sync_super_admin_password()

        async with engine.begin() as conn:
            async with rls_bypass(conn, "users", "super_admins", "staff_credentials"):
                row = (
                    await conn.execute(
                        text(
                            "SELECT u.id, sa.user_id IS NOT NULL AS is_sa,"
                            "       sc.user_id IS NOT NULL AS has_password"
                            " FROM users u"
                            " LEFT JOIN super_admins sa ON sa.user_id = u.id"
                            " LEFT JOIN staff_credentials sc ON sc.user_id = u.id"
                            " WHERE u.kind = 'staff' AND lower(u.login) = :login"
                        ),
                        {"login": login},
                    )
                ).first()

        assert row is not None, "noma'lum login uchun hisob yaratilmadi"
        assert row.is_sa, "yaratilgan hisob super admin emas"
        assert row.has_password, "yaratilgan hisobga parol qo'yilmadi"
    finally:
        # Sinov ortidan bazada HAQIQIY super admin hisobi qolib ketmasin
        async with engine.begin() as conn:
            async with rls_bypass(conn, "users", "super_admins", "staff_credentials"):
                await conn.execute(
                    text(
                        "DELETE FROM staff_credentials WHERE user_id IN"
                        " (SELECT id FROM users WHERE kind = 'staff' AND lower(login) = :login)"
                    ),
                    {"login": login},
                )
                await conn.execute(
                    text(
                        "DELETE FROM super_admins WHERE user_id IN"
                        " (SELECT id FROM users WHERE kind = 'staff' AND lower(login) = :login)"
                    ),
                    {"login": login},
                )
                await conn.execute(
                    text("DELETE FROM users WHERE kind = 'staff' AND lower(login) = :login"),
                    {"login": login},
                )
        await engine.dispose()


@skip_no_db
async def test_too_short_password_is_rejected(account: int) -> None:
    """SUPER_ADMIN minimumi (16 belgi) shu yo'lda ham amal qiladi."""
    settings.super_admin_logins = LOGIN
    settings.super_admin_password = SecretStr("qisqa parol")

    await sync_super_admin_password()

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "staff_credentials"):
            exists = await conn.scalar(
                text("SELECT 1 FROM staff_credentials WHERE user_id = :uid"), {"uid": account}
            )
    await engine.dispose()

    assert exists is None
