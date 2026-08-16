"""Bot admin menyusi — kunlik tushum/xarajat/analitika (reja #29, 2026-08-16).

Haqiqiy PostgreSQL va Redis talab qiladi:
    docker compose up -d postgres redis
    RUN_DB_TESTS=1 pytest
"""

import hashlib
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import null_actor_refs, rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.main import app

pytestmark = pytest.mark.asyncio

WEBHOOK_SECRET = "botmenu-test-secret"  # noqa: S105
WEBHOOK_HEADER_VALUE = hashlib.sha256(WEBHOOK_SECRET.encode()).hexdigest()
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

OWNER_TG = 900_100_001
STAFF_TG = 900_100_002
UNLINKED_TG = 900_100_003

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.tg_webhook_secret, "get_secret_value", lambda: WEBHOOK_SECRET)


@pytest.fixture(autouse=True)
def _capture_telegram(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, Any]]]:
    """Haqiqiy Telegram API'ga chiqmaslik uchun yuborilgan xabar/ack'larni ushlab oladi."""
    sent: list[dict[str, Any]] = []
    acked: list[dict[str, Any]] = []

    async def fake_send_message(
        token: str, chat_id: int, text: str, *, reply_markup: dict[str, Any] | None = None
    ) -> None:
        sent.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def fake_answer_callback_query(
        token: str, callback_query_id: str, text: str | None = None
    ) -> None:
        acked.append({"id": callback_query_id, "text": text})

    monkeypatch.setattr(telegram_api, "send_message", fake_send_message)
    monkeypatch.setattr(telegram_api, "answer_callback_query", fake_answer_callback_query)
    return {"sent": sent, "acked": acked}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def club_graph() -> AsyncIterator[dict[str, int]]:
    """OWNER (bog'langan) + STAFF (bog'langan) + bo'sh klub.

    `[[playbron-fixture-rls-bypass]]`: butun graf nol'dan quriladi, hali
    tabiiy aktor yo'q — `rls_bypass` shart.
    """
    engine = _owner_engine()
    scoped = ("users", "organizations", "clubs", "memberships", "staff_telegram")

    async with engine.begin() as conn:
        async with rls_bypass(conn, *scoped):
            owner_id = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'botmenu.test.owner', 'active', 'Egasi')"
                    " RETURNING id"
                )
            )
            staff_id = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'botmenu.test.staff', 'active', 'Xodim')"
                    " RETURNING id"
                )
            )
            org_id = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status)"
                    " VALUES (:o, 'Botmenu Test Org', 'active') RETURNING id"
                ),
                {"o": owner_id},
            )
            club_id = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'Botmenu Test Club', 'active') RETURNING id"
                ),
                {"o": org_id},
            )
            for uid, role in ((owner_id, "OWNER"), (staff_id, "STAFF")):
                await conn.execute(
                    text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                    {"u": uid, "c": club_id, "r": role},
                )
            for uid, tg in ((owner_id, OWNER_TG), (staff_id, STAFF_TG)):
                await conn.execute(
                    text(
                        "INSERT INTO staff_telegram (user_id, telegram_id, chat_id, linked_at)"
                        " VALUES (:u, :tg, :tg, now())"
                    ),
                    {"u": uid, "tg": tg},
                )

    yield {"owner_id": owner_id, "staff_id": staff_id, "org_id": org_id, "club_id": club_id}

    async with engine.begin() as conn:
        async with rls_bypass(conn, *scoped):
            await conn.execute(
                text("DELETE FROM staff_telegram WHERE user_id IN (:o, :s)"),
                {"o": owner_id, "s": staff_id},
            )
            await conn.execute(text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
            await conn.execute(text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
            await conn.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
            await null_actor_refs(conn, owner_id, staff_id)
            await conn.execute(
                text("DELETE FROM users WHERE id IN (:o, :s)"), {"o": owner_id, "s": staff_id}
            )
    await engine.dispose()


def _text_update(tg_id: int, text_: str = "salom") -> dict[str, Any]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "text": text_,
            "from": {"id": tg_id, "first_name": "Sinov"},
            "chat": {"id": tg_id, "type": "private"},
        },
    }


def _callback_update(tg_id: int, data: str) -> dict[str, Any]:
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cbq1",
            "data": data,
            "from": {"id": tg_id},
            "message": {"chat": {"id": tg_id}},
        },
    }


# ── Matnli xabar → menyu ─────────────────────────────────────────────────


@skip_no_db
async def test_owner_gets_menu_on_plain_text(
    client: httpx.AsyncClient,
    club_graph: dict[str, int],
    _capture_telegram: dict[str, list[dict[str, Any]]],
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_text_update(OWNER_TG),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    assert len(_capture_telegram["sent"]) == 1
    sent = _capture_telegram["sent"][0]
    assert sent["chat_id"] == OWNER_TG
    assert sent["reply_markup"]["inline_keyboard"]  # 3 tugma


@skip_no_db
async def test_staff_gets_no_menu(
    client: httpx.AsyncClient,
    club_graph: dict[str, int],
    _capture_telegram: dict[str, list[dict[str, Any]]],
) -> None:
    """Oddiy xodim (STAFF) — moliyaviy hisobot uni qiziqtirmasligi kerak."""
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_text_update(STAFF_TG),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    assert _capture_telegram["sent"] == []


@skip_no_db
async def test_unlinked_sender_gets_no_menu(
    client: httpx.AsyncClient,
    _capture_telegram: dict[str, list[dict[str, Any]]],
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_text_update(UNLINKED_TG),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    assert _capture_telegram["sent"] == []


# ── Tugma bosilishi → hisobot ─────────────────────────────────────────────


@skip_no_db
@pytest.mark.parametrize(
    ("data", "expect_snippet"),
    [
        ("menu:daily", "Kunlik hisobot"),
        ("menu:expenses", "Xarajatlar hisoboti"),
        ("menu:analytics", "Analitika"),
    ],
)
async def test_callback_sends_matching_report(
    client: httpx.AsyncClient,
    club_graph: dict[str, int],
    _capture_telegram: dict[str, list[dict[str, Any]]],
    data: str,
    expect_snippet: str,
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_callback_update(OWNER_TG, data),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    # Telegram'ning "yuklanmoqda" soatchasi albatta yopilishi kerak
    assert len(_capture_telegram["acked"]) == 1
    assert _capture_telegram["acked"][0]["id"] == "cbq1"
    assert len(_capture_telegram["sent"]) == 1
    assert expect_snippet in _capture_telegram["sent"][0]["text"]
    assert club_graph["club_id"] is not None


@skip_no_db
async def test_callback_from_staff_is_refused(
    client: httpx.AsyncClient,
    club_graph: dict[str, int],
    _capture_telegram: dict[str, list[dict[str, Any]]],
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_callback_update(STAFF_TG, "menu:daily"),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    assert len(_capture_telegram["acked"]) == 1
    # Ack bor, lekin hisobot yo'q — ruxsat rad etilgani haqidagi xabar keladi
    assert len(_capture_telegram["sent"]) == 1
    assert "ruxsat yo'q" in _capture_telegram["sent"][0]["text"]


@skip_no_db
async def test_unknown_callback_data_is_acked_but_silent(
    client: httpx.AsyncClient,
    club_graph: dict[str, int],
    _capture_telegram: dict[str, list[dict[str, Any]]],
) -> None:
    r = await client.post(
        "/api/v1/auth/telegram/webhook/admin",
        json=_callback_update(OWNER_TG, "menu:unknown"),
        headers={SECRET_HEADER: WEBHOOK_HEADER_VALUE},
    )
    assert r.status_code == 200
    assert len(_capture_telegram["acked"]) == 1
    assert _capture_telegram["sent"] == []
