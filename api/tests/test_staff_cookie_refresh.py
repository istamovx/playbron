"""Xodim refresh tokeni — HttpOnly cookie (audit §10, faqat ADMIN konsoli).

Mijoz (Mini App) oqimi bugungidek body orqali — shu fayl ALOHIDA
tekshiradi (`test_stray_staff_cookie_does_not_hijack_customer_refresh`)
ikkalasi bir brauzerda aralashmasligini.
"""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from conftest import rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.core.passwords import hash_password
from playbron.main import app
from playbron.modules.auth.router import STAFF_REFRESH_COOKIE

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

LOGIN = "cookie.sinov"
PASSWORD = "juda mustahkam parol"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    from playbron.core.redis import redis_client

    async def wipe() -> None:
        redis = redis_client()
        keys = [key async for key in redis.scan_iter(match="rl:*")]
        if keys:
            await redis.delete(*keys)

    await wipe()
    yield
    await wipe()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    # Cookie jar kerak — `httpx.AsyncClient`ning o'zi Set-Cookie'ni
    # avtomatik saqlaydi va keyingi so'rovda qaytaradi (brauzer kabi).
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def staff_user() -> AsyncIterator[int]:
    engine = _owner_engine()
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "staff_credentials"):
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
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false)"
                    " ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false,"
                    "     failed_count = 0"
                ),
                {"uid": user_id, "h": password_hash},
            )

    yield int(user_id)

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users"):
            await conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    await engine.dispose()


@skip_no_db
async def test_login_sets_cookie_and_omits_body_token(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    r = await client.post("/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["refresh_token"] is None, "xodim javobida refresh_token ENDI ko'rinmasligi kerak"
    assert body["access_token"]

    assert STAFF_REFRESH_COOKIE in client.cookies, "login cookie o'rnatmadi"
    raw_cookie = client.cookies[STAFF_REFRESH_COOKIE]
    assert raw_cookie  # bo'sh emas


@skip_no_db
async def test_refresh_via_cookie_rotates_without_body(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    login = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    old_cookie = client.cookies[STAFF_REFRESH_COOKIE]

    # Body ATAYLAB bo'sh — `packages/api-client` cookie rejimida shunday
    # yuboradi (`client.ts::refresh()`).
    r = await client.post("/api/v1/auth/refresh", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refresh_token"] is None
    assert body["access_token"]

    new_cookie = client.cookies[STAFF_REFRESH_COOKIE]
    assert new_cookie != old_cookie, "rotatsiyada cookie yangilanmadi"


@skip_no_db
async def test_reused_cookie_token_is_detected_as_theft(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Eski (allaqachon ishlatilgan) cookie qiymati qayta yuborilsa —
    o'g'irlangan deb hisoblanadi, `service.rotate_refresh()`dagi bilan
    bir xil invariant, faqat transport cookie."""
    login = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    old_cookie = client.cookies[STAFF_REFRESH_COOKIE]

    first = await client.post("/api/v1/auth/refresh", json={})
    assert first.status_code == 200, first.text

    # Eski qiymatni QO'LDA qayta yuboramiz — xuddi o'g'irlangan cookie
    # qaytadan ishlatilgandek.
    stale_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={STAFF_REFRESH_COOKIE: old_cookie},
    )
    try:
        replay = await stale_client.post("/api/v1/auth/refresh", json={})
        assert replay.status_code == 401, replay.text
        assert replay.json()["error"]["code"] == "REFRESH_REUSED"
    finally:
        await stale_client.aclose()

    # Zanjir butunlay bekor qilingan — YANGI (aslida haqiqiy) token ham endi ishlamaydi.
    revoked = await client.post("/api/v1/auth/refresh", json={})
    assert revoked.status_code == 401, revoked.text


@skip_no_db
async def test_logout_via_cookie_clears_cookie_and_revokes(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    login = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    access = login.json()["access_token"]

    logout = await client.post(
        "/api/v1/auth/logout", json={}, headers={"Authorization": f"Bearer {access}"}
    )
    assert logout.status_code == 204, logout.text

    # Brauzer cookie'si tozalangan (`delete_cookie` — bo'sh qiymat/eskirgan)
    assert client.cookies.get(STAFF_REFRESH_COOKIE) in (None, "")

    again = await client.post("/api/v1/auth/refresh", json={})
    assert again.status_code == 401, "logout'dan keyin cookie baribir ishlab qoldi"


@skip_no_db
async def test_customer_token_forged_into_staff_cookie_is_rejected(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Himoya qatlami: `pb_staff_refresh` nomli cookie'da CUSTOMER turdagi
    token bo'lsa ham server buni STAFF sessiyasi sifatida QABUL QILMAYDI
    (`router.py::refresh()` — `payload["kind"] != AUDIENCE_STAFF`)."""
    dev_login = await client.post(
        "/api/v1/auth/dev/login", json={"telegram_id": 970_555_222, "first_name": "Mijoz"}
    )
    assert dev_login.status_code == 200, dev_login.text
    customer_token = dev_login.json()["refresh_token"]

    forged_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={STAFF_REFRESH_COOKIE: customer_token},
    )
    try:
        r = await forged_client.post("/api/v1/auth/refresh", json={})
        assert r.status_code == 401, r.text
        assert r.json()["error"]["code"] == "REFRESH_INVALID"
    finally:
        await forged_client.aclose()

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "users"):
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = 970555222 AND kind = 'customer'")
            )
    await engine.dispose()


@skip_no_db
async def test_stray_staff_cookie_does_not_hijack_customer_refresh(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Bitta brauzerda ham xodim (cookie), ham mijoz (body) sessiyasi ochiq
    bo'lsa — mijoz sahifasidagi so'rov xodim cookie'sini ISHLATMAYDI."""
    login = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    assert STAFF_REFRESH_COOKIE in client.cookies

    dev_login = await client.post(
        "/api/v1/auth/dev/login", json={"telegram_id": 970_555_111, "first_name": "Mijoz"}
    )
    assert dev_login.status_code == 200, dev_login.text
    customer_refresh_token = dev_login.json()["refresh_token"]
    assert customer_refresh_token

    # SHU client'da xodim cookie'si HAM bor — server body'ni ustuvor olishi kerak.
    r = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": customer_refresh_token}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refresh_token"], "mijoz javobida token yo'q — body ustuvor bo'lishi kerak edi"
    assert body["refresh_token"] != customer_refresh_token  # rotatsiyalangan, lekin BOR

    # Xodim cookie'si BUZILMAGAN — hali o'zi bilan yangilanadi.
    staff_refresh = await client.post("/api/v1/auth/refresh", json={})
    assert staff_refresh.status_code == 200, staff_refresh.text

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "users"):
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = 970555111 AND kind = 'customer'")
            )
    await engine.dispose()
