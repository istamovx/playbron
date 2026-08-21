"""Smena ochish semantikasi — `0033_shift_per_club_uk` regressiya qulfi.

Indeks `(club_id, staff_id) WHERE status='open'`: bitta klubda bitta ochiq
smena (409 SHIFT_ALREADY_OPEN), boshqa klubda parallel smena — mumkin.
Migratsiya self-testi DB invariantini qoplaydi; bu yerdagi ikkala test
xuddi shu qoidani API darajasida muzlatadi.
"""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from conftest import purge_audit_actor, rls_bypass
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

STAFF_LOGIN = "shiftuk.kassir"
PASSWORD = "juda mustahkam parol"


@pytest_asyncio.fixture
async def two_clubs() -> AsyncIterator[dict[str, int]]:
    """Bitta xodim IKKI klubda — `memberships` ataylab qo'llagan holat."""
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "staff_credentials"
        ):
            ids["staff"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'Kassir')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": STAFF_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["staff"], "h": password_hash},
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'ShiftUK Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["staff"]},
            )
            for key in ("club_a", "club_b"):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status, opens_at_min, closes_at_min)"
                        " VALUES (:o, :n, 'active', 0, 1440) RETURNING id"
                    ),
                    {"o": ids["org"], "n": f"ShiftUK {key}"},
                )
                await conn.execute(
                    text(
                        "INSERT INTO memberships (user_id, club_id, role)"
                        " VALUES (:u, :c, 'STAFF')"
                        " ON CONFLICT (user_id, club_id) DO UPDATE SET status = 'active'"
                    ),
                    {"u": ids["staff"], "c": ids[key]},
                )

    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "organizations", "shifts"):
            await purge_audit_actor(conn, ids["staff"])
            await conn.execute(
                text("DELETE FROM shifts WHERE club_id IN (:a, :b)"),
                {"a": ids["club_a"], "b": ids["club_b"]},
            )
            await conn.execute(
                text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]}
            )
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"),
                {"l": STAFF_LOGIN},
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _headers(client: httpx.AsyncClient, club_id: int) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": STAFF_LOGIN, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


@skip_no_db
async def test_open_shift_twice_in_same_club_is_rejected(
    client: httpx.AsyncClient, two_clubs: dict[str, int]
) -> None:
    club = two_clubs["club_a"]
    headers = await _headers(client, club)

    r = await client.post(
        f"/api/v1/clubs/{club}/shifts", json={"opening_cash": 0}, headers=headers
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        f"/api/v1/clubs/{club}/shifts", json={"opening_cash": 0}, headers=headers
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "SHIFT_ALREADY_OPEN"


@skip_no_db
async def test_staff_opens_parallel_shift_in_second_club(
    client: httpx.AsyncClient, two_clubs: dict[str, int]
) -> None:
    """0033 tuzatgan xatti-harakat: ikkinchi klubda smena ochish mumkin."""
    headers_a = await _headers(client, two_clubs["club_a"])
    r = await client.post(
        f"/api/v1/clubs/{two_clubs['club_a']}/shifts", json={"opening_cash": 0}, headers=headers_a
    )
    assert r.status_code == 201, r.text

    headers_b = await _headers(client, two_clubs["club_b"])
    r = await client.post(
        f"/api/v1/clubs/{two_clubs['club_b']}/shifts", json={"opening_cash": 0}, headers=headers_b
    )
    # 0033 dan oldin bu yerda 409 chiqardi — indeks staff_id bo'yicha global edi
    assert r.status_code == 201, r.text
