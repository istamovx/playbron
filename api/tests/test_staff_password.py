"""Parolni almashtirish — `must_change` oqimi va sessiya bekor qilinishi."""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.core.passwords import hash_password
from playbron.main import app

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

LOGIN = "sinov.parol"
OLD = "eski mustahkam parol"
NEW = "yangi mustahkam parol"


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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def staff_user() -> AsyncIterator[int]:
    """`must_change = true` bilan — birov bergan parol holati."""
    engine = _owner_engine()
    password_hash = await hash_password(OLD)

    async with engine.begin() as conn:
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
                " VALUES (:uid, :h, true)"
                " ON CONFLICT (user_id) DO UPDATE"
                " SET password_hash = EXCLUDED.password_hash, must_change = true,"
                "     failed_count = 0"
            ),
            {"uid": user_id, "h": password_hash},
        )

    yield int(user_id)

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    await engine.dispose()


async def _login(client: httpx.AsyncClient, password: str) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": password}
    )


@skip_no_db
async def test_assigned_password_demands_change(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Birov bergan parol bir martalik — Ilova C.2."""
    r = await _login(client, OLD)
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is True


@skip_no_db
async def test_wrong_current_password_is_rejected(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Sessiyasi o'g'irlangan hujumchi parolni jimgina almashtirolmasin."""
    token = (await _login(client, OLD)).json()["access_token"]

    r = await client.post(
        "/api/v1/auth/staff/password/change",
        json={"current_password": "boshqa parol", "new_password": NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "LOGIN_INVALID"


@skip_no_db
async def test_change_succeeds_and_old_password_stops_working(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    token = (await _login(client, OLD)).json()["access_token"]

    changed = await client.post(
        "/api/v1/auth/staff/password/change",
        json={"current_password": OLD, "new_password": NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert changed.status_code == 200, changed.text
    # Yangi sessiya darhol beriladi — foydalanuvchi ikki marta kirmaydi
    assert changed.json()["access_token"]
    assert changed.json()["must_change_password"] is False

    assert (await _login(client, OLD)).status_code == 401
    fresh = await _login(client, NEW)
    assert fresh.status_code == 200, fresh.text
    # Talab bajarildi
    assert fresh.json()["must_change_password"] is False


@skip_no_db
async def test_short_password_is_rejected_with_reason(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Sabab aytiladi — «parol mos emas» foydalanuvchini taxminga majburlaydi."""
    token = (await _login(client, OLD)).json()["access_token"]

    r = await client.post(
        "/api/v1/auth/staff/password/change",
        json={"current_password": OLD, "new_password": "qisqa"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PASSWORD_TOO_SHORT"


@skip_no_db
async def test_same_password_is_rejected(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    token = (await _login(client, OLD)).json()["access_token"]

    r = await client.post(
        "/api/v1/auth/staff/password/change",
        json={"current_password": OLD, "new_password": OLD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PASSWORD_UNCHANGED"
