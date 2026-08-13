"""Uchidan-uchiga auth oqimi — HTTP qatlami, DB va RLS birga.

Bu testlar haqiqiy PostgreSQL va Redis talab qiladi:
    docker compose up -d postgres redis
    RUN_DB_TESTS=1 pytest
"""

import hashlib
import hmac
import json
import os
import time
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.main import app

pytestmark = pytest.mark.asyncio

BOT = "123456:FLOW-TEST"  # noqa: S105
CLIENT_TG = 900_000_001
OWNER_TG = 900_000_002

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)


@pytest.fixture(autouse=True)
def _bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.bot_token, "get_secret_value", lambda: BOT)


def init_data(telegram_id: int, nonce: str) -> str:
    fields = {
        "user": json.dumps(
            {"id": telegram_id, "first_name": "Test", "username": f"u{telegram_id}"},
            separators=(",", ":"),
        ),
        "auth_date": str(int(time.time())),
        "query_id": nonce,
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def club_owner() -> AsyncIterator[dict[str, int]]:
    """Tarifi bor tashkilot, klub va OWNER a'zoligi."""
    engine = _owner_engine()
    ids: dict[str, int] = {}

    async with engine.begin() as conn:
        ids["user"] = await conn.scalar(
            text(
                "INSERT INTO users (telegram_id, first_name) VALUES (:tid, 'Owner')"
                " ON CONFLICT (telegram_id) DO UPDATE SET first_name = 'Owner' RETURNING id"
            ),
            {"tid": OWNER_TG},
        )
        ids["org"] = await conn.scalar(
            text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:u, 'Flow Org', 'active', 'gold') RETURNING id"
            ),
            {"u": ids["user"]},
        )
        ids["club"] = await conn.scalar(
            text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'Flow Club', 'active')"
                " RETURNING id"
            ),
            {"o": ids["org"]},
        )
        await conn.execute(
            text(
                "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"
                " ON CONFLICT DO NOTHING"
            ),
            {"u": ids["user"], "c": ids["club"]},
        )

    yield ids

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
        await conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": ids["user"]})
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_client_user() -> AsyncIterator[None]:
    engine = _owner_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE telegram_id = :t"), {"t": CLIENT_TG})
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE telegram_id = :t"), {"t": CLIENT_TG})
    await engine.dispose()


# ── Mijoz oqimi ───────────────────────────────────────────────────────────


@skip_no_db
async def test_client_sign_in_creates_user(
    client: httpx.AsyncClient, clean_client_user: None
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/initdata", json={"init_data": init_data(CLIENT_TG, "c1")}
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["user"]["telegram_id"] == CLIENT_TG
    # Mijoz global — hech qanday klubga bog'lanmagan
    assert body["memberships"] == []
    assert body["is_super_admin"] is False
    # initData telefonni bermaydi
    assert body["user"]["phone"] is None
    assert body["user"]["phone_verified"] is False


@skip_no_db
async def test_replay_is_rejected(client: httpx.AsyncClient, clean_client_user: None) -> None:
    payload = init_data(CLIENT_TG, "c2")

    first = await client.post("/api/v1/auth/telegram/initdata", json={"init_data": payload})
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/telegram/initdata", json={"init_data": payload})
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "AUTH_REPLAY"


@skip_no_db
async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "NO_TOKEN"


# ── Refresh rotatsiyasi ───────────────────────────────────────────────────


@skip_no_db
async def test_refresh_rotates_and_detects_theft(
    client: httpx.AsyncClient, clean_client_user: None
) -> None:
    signed = await client.post(
        "/api/v1/auth/telegram/initdata", json={"init_data": init_data(CLIENT_TG, "c3")}
    )
    old = signed.json()["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert rotated.status_code == 200
    fresh = rotated.json()["refresh_token"]
    assert fresh != old, "har rotatsiyada yangi token berilishi kerak"

    # O'g'irlangan (allaqachon ishlatilgan) token
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "REFRESH_REUSED"

    # Zanjir buzilgach yangi token ham bekor bo'ladi
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": fresh})
    assert after.status_code == 401, "o'g'irlik aniqlangach barcha tokenlar bekor bo'lishi kerak"


@skip_no_db
async def test_logout_revokes_refresh(
    client: httpx.AsyncClient, clean_client_user: None
) -> None:
    signed = await client.post(
        "/api/v1/auth/telegram/initdata", json={"init_data": init_data(CLIENT_TG, "c4")}
    )
    session = signed.json()

    out = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": session["refresh_token"]},
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )
    assert out.status_code == 204, out.text

    again = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    assert again.status_code == 401


# ── Klub egasi va entitlement ─────────────────────────────────────────────


@skip_no_db
async def test_owner_sees_club_and_plan(
    client: httpx.AsyncClient, club_owner: dict[str, int]
) -> None:
    """RLS `app.org_id` ga tayanadi — usiz tarif ko'rinmay qoladi."""
    signed = await client.post(
        "/api/v1/auth/telegram/initdata", json={"init_data": init_data(OWNER_TG, "o1")}
    )
    assert signed.status_code == 200, signed.text
    session = signed.json()

    assert len(session["memberships"]) == 1
    assert session["memberships"][0]["club_id"] == club_owner["club"]
    assert session["memberships"][0]["role"] == "OWNER"

    headers = {"Authorization": f"Bearer {session['access_token']}"}

    me = await client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert [c["id"] for c in me.json()["clubs"]] == [club_owner["club"]]

    ent = await client.get("/api/v1/me/entitlements", headers=headers)
    assert ent.status_code == 200, ent.text
    body = ent.json()
    assert body["plan"] == "gold"
    assert "pos" in body["features"]
    assert body["limits"]["clubs"] == 1


@skip_no_db
async def test_foreign_club_header_is_rejected(
    client: httpx.AsyncClient, club_owner: dict[str, int]
) -> None:
    """Boshqa klubning `X-Club-Id` sarlavhasi bilan kirib bo'lmaydi."""
    signed = await client.post(
        "/api/v1/auth/telegram/initdata", json={"init_data": init_data(OWNER_TG, "o2")}
    )
    headers = {
        "Authorization": f"Bearer {signed.json()['access_token']}",
        "X-Club-Id": str(club_owner["club"] + 99_999),
    }

    r = await client.get("/api/v1/me", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CLUB_FORBIDDEN"
