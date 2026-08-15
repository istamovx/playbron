"""Xodim Telegram bog'lash — start → webhook → poll, so'ng bron bildirishnomasi
haqiqatan yetib borishini isbotlaydi.

Manba: `api/migrations/versions/0010_staff_telegram_link.py`. Bu fayl
`test_bookings.py` bilan bir xil `rls_bypass()` naqshidan foydalanadi, lekin
o'z klubini quradi — testlar orasida bog'liqlik yo'q.
"""

import hashlib
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

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
from playbron.modules.bookings import notify as booking_notify

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

WEBHOOK_SECRET = "stafflink-test-secret"  # noqa: S105
WEBHOOK_HEADER_VALUE = hashlib.sha256(WEBHOOK_SECRET.encode()).hexdigest()
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

OWNER_LOGIN = "tglink.owner"
PASSWORD = "juda mustahkam parol"
STAFF_TG = 970_000_222
CUSTOMER_TG = 970_000_333


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.tg_webhook_secret, "get_secret_value", lambda: WEBHOOK_SECRET)


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
async def world() -> AsyncIterator[dict[str, int]]:
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "stations", "staff_credentials"
        ):
            ids["owner"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'Ega')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": OWNER_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["owner"], "h": password_hash},
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'TgLink Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'TgLink Club', 'active') RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
                {"u": ids["owner"], "c": ids["club"]},
            )
            ids["station"] = await conn.scalar(
                text(
                    "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                    " VALUES (:c, 'TGL-1', 'Standart', 'ps5', 40000) RETURNING id"
                ),
                {"c": ids["club"]},
            )

    # `test_bookings.py::world`dagi bilan bir xil sabab — `rls_bypass()`ning
    # DDL'i asyncpg'ning tayyorlangan bayonot keshini eskirtiradi.
    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "bookings", "staff_telegram"):
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(
                text("DELETE FROM staff_telegram WHERE user_id = :u"), {"u": ids["owner"]}
            )
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"), {"l": OWNER_LOGIN}
            )
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = :tg AND kind = 'customer'"),
                {"tg": CUSTOMER_TG},
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _staff_headers(client: httpx.AsyncClient, club_id: int) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": OWNER_LOGIN, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


async def _customer_headers(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/dev/login", json={"telegram_id": CUSTOMER_TG, "first_name": "Sinov"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _link_update(nonce: str) -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "text": f"/start {nonce}",
            "from": {"id": STAFF_TG, "first_name": "Xodim", "language_code": "uz"},
            "chat": {"id": STAFF_TG, "type": "private"},
        },
    }


@skip_no_db
async def test_customer_cannot_start_link(client: httpx.AsyncClient) -> None:
    customer_h = await _customer_headers(client)
    r = await client.post("/api/v1/auth/telegram/link/start", headers=customer_h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "STAFF_TOKEN_REQUIRED"


@skip_no_db
async def test_full_link_flow_then_booking_notify_reaches_staff(
    client: httpx.AsyncClient, world: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    staff_h = await _staff_headers(client, world["club"])

    # 1. Konsolda "bog'lash" — nonce olinadi
    r = await client.post("/api/v1/auth/telegram/link/start", headers=staff_h)
    assert r.status_code == 200
    nonce = r.json()["nonce"]
    assert nonce.startswith("lnk_")

    # 2. Tasdiqqacha poll `pending`
    r = await client.post(f"/api/v1/auth/telegram/link/{nonce}", headers=staff_h)
    assert r.json()["status"] == "pending"

    # 3. Botda Start bosildi — webhook staff_telegram_link_confirm()ni chaqiradi
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_link_update(nonce),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200

    # 4. Poll `ready`, so'ng bir martalik — ikkinchi so'rov `expired`
    r = await client.post(f"/api/v1/auth/telegram/link/{nonce}", headers=staff_h)
    assert r.json()["status"] == "ready"
    r = await client.post(f"/api/v1/auth/telegram/link/{nonce}", headers=staff_h)
    assert r.json()["status"] == "expired"

    # 5. Haqiqiy isbot: mijoz bron yuborganda `booking_notify_targets()`
    #    ENDI shu xodimning `chat_id`sini topadi (`0010`dagi tuzatish) —
    #    Telegram API chaqiruvi o'zi tutib olinadi, tarmoqqa chiqilmaydi.
    sent: list[tuple[int, str]] = []

    async def fake_send(token: str, chat_id: int, text_body: str) -> None:  # noqa: ARG001
        sent.append((chat_id, text_body))

    monkeypatch.setattr(booking_notify.telegram_api, "send_message", fake_send)

    customer_h = await _customer_headers(client)
    starts = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": starts, "hours": 1},
        headers=customer_h,
    )
    assert r.status_code == 201, r.text

    assert sent, "xodimga bron bildirishnomasi yetib bormadi"
    assert sent[0][0] == STAFF_TG
