"""Bot orqali kirish oqimi — start → webhook → poll.

Haqiqiy PostgreSQL va Redis talab qiladi:
    docker compose up -d postgres redis
    RUN_DB_TESTS=1 pytest
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.main import app
from playbron.modules.auth import botlogin

pytestmark = pytest.mark.asyncio

WEBHOOK_SECRET = "botlogin-test-secret"  # noqa: S105
BOT_TG = 900_000_003
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.tg_webhook_secret, "get_secret_value", lambda: WEBHOOK_SECRET)


@pytest.fixture(autouse=True)
def _mute_notify(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Bot API'ga chiqmaslik uchun `notify` yozib olinadi."""
    calls: list[dict[str, Any]] = []

    async def fake_notify(chat_id: int, language_code: str | None, *, approved: bool) -> None:
        calls.append({"chat_id": chat_id, "lang": language_code, "approved": approved})

    monkeypatch.setattr(botlogin, "notify", fake_notify)
    return calls


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def clean_bot_user() -> AsyncIterator[None]:
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE telegram_id = :t"), {"t": BOT_TG})
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE telegram_id = :t"), {"t": BOT_TG})
    await engine.dispose()


def start_update(nonce: str, *, lang: str = "uz") -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "text": f"/start {nonce}",
            "from": {
                "id": BOT_TG,
                "first_name": "Bot",
                "username": "botuser",
                "language_code": lang,
            },
            "chat": {"id": BOT_TG, "type": "private"},
        },
    }


# ── Oqim ──────────────────────────────────────────────────────────────────


@skip_no_db
async def test_full_flow(
    client: httpx.AsyncClient,
    clean_bot_user: None,
    _mute_notify: list[dict[str, Any]],
) -> None:
    # 1. Start — nonce olinadi
    r = await client.post("/api/v1/auth/telegram/start")
    assert r.status_code == 200
    nonce = r.json()["nonce"]
    assert len(nonce) >= 32

    # 2. Tasdiqqacha poll `pending`
    r = await client.post(f"/api/v1/auth/telegram/start/{nonce}")
    assert r.json() == {"status": "pending", "session": None}

    # 3. Webhook — botda Start bosildi
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=start_update(nonce),
        headers={SECRET_HEADER: WEBHOOK_SECRET},
    )
    assert r.status_code == 200
    assert _mute_notify == [{"chat_id": BOT_TG, "lang": "uz", "approved": True}]

    # 4. Poll `ready` — to'liq sessiya bilan
    r = await client.post(f"/api/v1/auth/telegram/start/{nonce}")
    body = r.json()
    assert body["status"] == "ready"
    assert body["session"]["user"]["telegram_id"] == BOT_TG
    assert body["session"]["access_token"]

    # 5. Nonce bir marta ishlaydi
    r = await client.post(f"/api/v1/auth/telegram/start/{nonce}")
    assert r.json()["status"] == "expired"


@skip_no_db
async def test_webhook_requires_secret(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/auth/telegram/webhook/admin", json=start_update("x"))
    assert r.status_code == 401

    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=start_update("x"),
        headers={SECRET_HEADER: "noto'g'ri"},
    )
    assert r.status_code == 401


@skip_no_db
async def test_unknown_nonce(
    client: httpx.AsyncClient, _mute_notify: list[dict[str, Any]]
) -> None:
    # Begona nonce bilan webhook — 200, lekin tasdiqlanmaydi
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=start_update("begona-nonce"),
        headers={SECRET_HEADER: WEBHOOK_SECRET},
    )
    assert r.status_code == 200
    assert _mute_notify == [{"chat_id": BOT_TG, "lang": "uz", "approved": False}]

    # Poll ham hech narsa bermaydi
    r = await client.post("/api/v1/auth/telegram/start/begona-nonce")
    assert r.json()["status"] == "expired"


@skip_no_db
async def test_webhook_ignores_other_updates(
    client: httpx.AsyncClient, _mute_notify: list[dict[str, Any]]
) -> None:
    for update in (
        {},
        {"message": {"text": "salom", "from": {"id": BOT_TG}}},
        {"message": {"text": "/start", "from": {"id": BOT_TG}}},
        {"edited_message": {"text": "/start abc", "from": {"id": BOT_TG}}},
    ):
        r = await client.post(
            "/api/v1/auth/telegram/webhook/admin",
            json=update,
            headers={SECRET_HEADER: WEBHOOK_SECRET},
        )
        assert r.status_code == 200

    assert _mute_notify == []
