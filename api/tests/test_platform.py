"""Platforma paneli — super admin cross-tenant statistikasi.

Manba: `api/migrations/versions/0015_platform_stats.py`, loyiha egasining
so'rovi (2026-08-16): "Super admin roli uchun infografikalar".
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from conftest import rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import db as core_db
from playbron.core.config import settings
from playbron.core.passwords import hash_password
from playbron.main import app

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

SA_LOGIN = "plt.superadmin"
OWNER_A_LOGIN = "plt.owner.a"
OWNER_B_LOGIN = "plt.owner.b"
PASSWORD = "juda mustahkam parol platforma"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """Bir xil login'lar sinovlar orasida qayta ishlatiladi — chelak
    tozalanmasa keyingi sinov haqiqiy 200 emas 429 RATE_LIMITED olardi
    (`test_bookings.py::clean_limits` bilan bir xil naqsh)."""
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
async def world() -> AsyncIterator[dict[str, int]]:
    """Ikkita ALOHIDA tashkilot/klub/stansiya + har birida bittadan
    CONFIRMED bron (bugun) — cross-tenant agregatsiya shu ikkalasini
    ham qamrashi kerak. Bittasi ham tabiiy aktordan yaratilmagan."""
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn,
            "users",
            "organizations",
            "clubs",
            "memberships",
            "stations",
            "staff_credentials",
            "super_admins",
            "bookings",
        ):
            ids["sa_user"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'SA')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": SA_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO super_admins (user_id, note) VALUES (:u, 'test')"
                    " ON CONFLICT (user_id) DO NOTHING"
                ),
                {"u": ids["sa_user"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["sa_user"], "h": password_hash},
            )

            for tag, login in (("a", OWNER_A_LOGIN), ("b", OWNER_B_LOGIN)):
                owner_id = await conn.scalar(
                    text(
                        "INSERT INTO users (kind, login, status, first_name)"
                        " VALUES ('staff', :login, 'active', 'Ega')"
                        " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                        " DO UPDATE SET status = 'active' RETURNING id"
                    ),
                    {"login": login},
                )
                await conn.execute(
                    text(
                        "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                        " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                        " SET password_hash = EXCLUDED.password_hash, must_change = false"
                    ),
                    {"uid": owner_id, "h": password_hash},
                )
                org_id = await conn.scalar(
                    text(
                        "INSERT INTO organizations (owner_user_id, name, status)"
                        " VALUES (:u, :n, 'active') RETURNING id"
                    ),
                    {"u": owner_id, "n": f"Platform Org {tag.upper()}"},
                )
                club_id = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status)"
                        " VALUES (:o, :n, 'active') RETURNING id"
                    ),
                    {"o": org_id, "n": f"Platform Club {tag.upper()}"},
                )
                await conn.execute(
                    text(
                        "INSERT INTO memberships (user_id, club_id, role)"
                        " VALUES (:u, :c, 'OWNER')"
                    ),
                    {"u": owner_id, "c": club_id},
                )
                station_id = await conn.scalar(
                    text(
                        "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                        " VALUES (:c, 'PLT-1', 'Standart', 'ps5', 30000) RETURNING id"
                    ),
                    {"c": club_id},
                )
                starts = datetime.now(UTC) - timedelta(minutes=10)
                await conn.execute(
                    text(
                        "INSERT INTO bookings"
                        " (club_id, station_id, guest_name, guest_phone, source, status,"
                        "  period, hours, rate_snapshot)"
                        " VALUES (:c, :s, 'Sinov', '+998900000000', 'STAFF', 'CONFIRMED',"
                        "         tstzrange(CAST(:starts AS timestamptz),"
                        "                   CAST(:starts AS timestamptz) + interval '1 hour'),"
                        "         1, 30000)"
                    ),
                    {"c": club_id, "s": station_id, "starts": starts},
                )
                ids[f"owner_{tag}"] = owner_id
                ids[f"org_{tag}"] = org_id
                ids[f"club_{tag}"] = club_id

    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "super_admins", "bookings"):
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :a OR club_id = :b"),
                                {"a": ids["club_a"], "b": ids["club_b"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :a OR id = :b"),
                                {"a": ids["org_a"], "b": ids["org_b"]})
            await conn.execute(text("DELETE FROM super_admins WHERE user_id = :u"),
                                {"u": ids["sa_user"]})
            await conn.execute(
                text(
                    "DELETE FROM users WHERE login IN (:sa, :a, :b) AND kind = 'staff'"
                ),
                {"sa": SA_LOGIN, "a": OWNER_A_LOGIN, "b": OWNER_B_LOGIN},
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient, login: str) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@skip_no_db
async def test_regular_owner_gets_404(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    """`require_super_admin` — panel borligi bilinmasin (403 emas, 404)."""
    owner_h = await _login(client, OWNER_A_LOGIN)
    r = await client.get("/api/v1/platform/stats", headers=owner_h)
    assert r.status_code == 404, r.text


@skip_no_db
async def test_super_admin_sees_cross_tenant_stats(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)
    r = await client.get("/api/v1/platform/stats", headers=sa_h)
    assert r.status_code == 200, r.text
    body = r.json()

    # `>=` — real (lokal) bazada boshqa klublar/bronlar ham bo'lishi mumkin;
    # bu yerda faqat "ikkalasi ham qo'shildi" tekshiriladi, aniq son emas
    # (`top_clubs` esa boshqa haqiqiy klublar ko'proq bron qilgan bo'lsa
    # bizning ikkitamizni siqib chiqarishi mumkin — shu sabab nomiga
    # tayanilmaydi, faqat shaklga).
    assert body["organizations_total"] >= 2
    assert body["clubs_active"] >= 2
    assert body["bookings_today"] >= 2
    assert body["revenue_today"] >= 60000
    assert isinstance(body["top_clubs"], list)
    for row in body["top_clubs"]:
        assert {"club_id", "club_name", "org_name", "bookings"} <= row.keys()
