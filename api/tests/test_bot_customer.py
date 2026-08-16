"""Mijoz boti — `/start` → ism → telefon → Mini App.

Telegram chaqiruvlari yozib olinadi, tarmoqqa chiqilmaydi.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.main import app
from playbron.modules.bot.router import SURFACE_CUSTOMER, webhook_secret

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

TG = 950_000_777
PHONE = "+998901112233"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture
async def sent(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[list[dict[str, Any]]]:
    """Telegram'ga ketadigan chaqiruvlar shu ro'yxatga tushadi."""
    calls: list[dict[str, Any]] = []

    async def fake_call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append({"method": method, **payload})
        return {}

    monkeypatch.setattr(telegram_api, "call", fake_call)
    yield calls


@pytest_asyncio.fixture
async def clean() -> AsyncIterator[None]:
    from playbron.core.redis import redis_client

    async def wipe() -> None:
        redis = redis_client()
        for pattern in (f"bot:fsm:cust:{TG}", f"bot:quiet:cust:{TG}", "tg:upd:customer:*"):
            keys = [k async for k in redis.scan_iter(match=pattern)]
            if keys:
                await redis.delete(*keys)

        engine = _owner_engine()
        async with engine.begin() as conn:
            # Tabiiy aktor yo'q (mijoz o'chirilmoqda, kirish emas) —
            # `rls_bypass` (`conftest.py`).
            async with rls_bypass(conn, "users"):
                await conn.execute(
                    text("DELETE FROM users WHERE kind = 'customer' AND telegram_id = :t"),
                    {"t": TG},
                )
        await engine.dispose()

    await wipe()
    yield
    await wipe()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _headers(*, valid: bool = True) -> dict[str, str]:
    token = webhook_secret(SURFACE_CUSTOMER) if valid else "boshqa-sekret"
    return {"X-Telegram-Bot-Api-Secret-Token": token}


def _msg(update_id: int, **over: Any) -> dict[str, Any]:
    message: dict[str, Any] = {
        "from": {"id": TG, "first_name": "Aziz", "language_code": "uz"},
        "chat": {"id": TG, "type": "private"},
    }
    message.update(over)
    return {"update_id": update_id, "message": message}


async def _phone_in_db() -> str | None:
    engine = _owner_engine()
    async with engine.begin() as conn:
        # `app.telegram_id` o'rnatilmagan — `users_self` GUC'siz hech qanday
        # mijoz qatorini ochmaydi, shuning uchun `rls_bypass` (`conftest.py`).
        async with rls_bypass(conn, "users"):
            row = (
                await conn.execute(
                    text("SELECT phone FROM users WHERE kind = 'customer' AND telegram_id = :t"),
                    {"t": TG},
                )
            ).first()
    await engine.dispose()
    return None if row is None else row[0]


@skip_no_db
async def test_full_registration_flow(
    client: httpx.AsyncClient, sent: list[dict[str, Any]], clean: None
) -> None:
    """`/start` → ismni tasdiqlash → kontakt → Mini App tugmasi."""
    r = await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(1, text="/start"), headers=_headers()
    )
    assert r.status_code == 200
    assert "Aziz" in sent[-1]["text"]

    # Ismni bir bosishda tasdiqlash
    await client.post(
        "/api/v1/telegram/webhook/main",
        json=_msg(2, text="✅ Ha, shu"),
        headers=_headers(),
    )
    assert "raqamingizni" in sent[-1]["text"]
    # Qo'lda yozib bo'lmasligi uchun `request_contact` tugmasi beriladi
    assert sent[-1]["reply_markup"]["keyboard"][0][0]["request_contact"] is True

    await client.post(
        "/api/v1/telegram/webhook/main",
        json=_msg(
            3,
            contact={"user_id": TG, "phone_number": PHONE},
        ),
        headers=_headers(),
    )

    assert await _phone_in_db() == PHONE
    assert any("web_app" in str(call.get("reply_markup", "")) for call in sent)


@skip_no_db
async def test_typed_phone_is_not_accepted(
    client: httpx.AsyncClient, sent: list[dict[str, Any]], clean: None
) -> None:
    """Qo'lda yozilgan raqam qabul qilinmaydi — tasdiqning butun ma'nosi shunda."""
    await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(10, text="/start"), headers=_headers()
    )
    await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(11, text="✅ Ha, shu"), headers=_headers()
    )
    await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(12, text=PHONE), headers=_headers()
    )

    assert await _phone_in_db() is None
    assert "qo‘lda" in sent[-1]["text"]


@skip_no_db
async def test_foreign_contact_is_rejected(
    client: httpx.AsyncClient, sent: list[dict[str, Any]], clean: None
) -> None:
    """Address book'dan boshqa odamning raqami."""
    await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(20, text="/start"), headers=_headers()
    )
    await client.post(
        "/api/v1/telegram/webhook/main", json=_msg(21, text="✅ Ha, shu"), headers=_headers()
    )
    await client.post(
        "/api/v1/telegram/webhook/main",
        json=_msg(22, contact={"user_id": 111_222, "phone_number": "+998900000000"}),
        headers=_headers(),
    )

    assert await _phone_in_db() is None
    assert "boshqa odamning" in sent[-1]["text"]


@skip_no_db
async def test_wrong_secret_changes_nothing_but_returns_200(
    client: httpx.AsyncClient, sent: list[dict[str, Any]], clean: None
) -> None:
    """Sekret mos kelmasa ham 200 — aks holda Telegram navbati to'xtaydi."""
    r = await client.post(
        "/api/v1/telegram/webhook/main",
        json=_msg(30, text="/start"),
        headers=_headers(valid=False),
    )
    assert r.status_code == 200
    assert sent == []


@skip_no_db
async def test_duplicate_update_is_processed_once(
    client: httpx.AsyncClient, sent: list[dict[str, Any]], clean: None
) -> None:
    """Takroriy `update_id` — ikkinchisi jimgina tashlanadi."""
    payload = _msg(40, text="/start")
    await client.post("/api/v1/telegram/webhook/main", json=payload, headers=_headers())
    first = len(sent)

    await client.post("/api/v1/telegram/webhook/main", json=payload, headers=_headers())
    assert len(sent) == first
