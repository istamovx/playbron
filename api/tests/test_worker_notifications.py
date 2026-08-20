"""Bildirishnoma qatlami — dedup va yuborish oqimi (jonli DB).

    docker compose up -d postgres redis
    RUN_DB_TESTS=1 pytest tests/test_worker_notifications.py
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from conftest import rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.core.db import AppSession
from playbron.worker.base import mark_job_writer
from playbron.worker.notify import queue_notification, send_pending

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

CHAT = 555_000_777


@pytest.fixture(autouse=True)
def _bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.bot_token, "get_secret_value", lambda: "123:NOTIFY-TEST")


@pytest_asyncio.fixture
async def club() -> AsyncIterator[dict[str, int]]:
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    ids: dict[str, int] = {}
    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "organizations", "clubs"):
            ids["user"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'notify.probe', 'active', 'Probe')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                )
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status)"
                    " VALUES (:u, 'Notify Org', 'active') RETURNING id"
                ),
                {"u": ids["user"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'Notify Club', 'active') RETURNING id"
                ),
                {"o": ids["org"]},
            )
    yield ids
    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "organizations", "notifications"):
            await conn.execute(
                text("DELETE FROM notifications WHERE club_id = :c"), {"c": ids["club"]}
            )
            await conn.execute(
                text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]}
            )
            await conn.execute(
                text("DELETE FROM users WHERE login = 'notify.probe' AND kind = 'staff'")
            )
    await engine.dispose()


async def _queue(club_id: int, *, entity_id: int = 1) -> int | None:
    async with AppSession() as session:
        async with session.begin():
            return await queue_notification(
                session,
                club_id=club_id,
                recipient_kind="CUSTOMER",
                chat_id=CHAT,
                template="booking_reminder_2h",
                entity_id=entity_id,
                payload={"club": "Notify Club", "station": "PS-1", "starts_at": "18:00"},
            )


async def _status(club_id: int) -> list[tuple[str, int]]:
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            rows = (
                await session.execute(
                    text(
                        "SELECT status, attempts FROM notifications WHERE club_id = :c"
                        " ORDER BY id"
                    ),
                    {"c": club_id},
                )
            ).all()
    return [(r.status, int(r.attempts)) for r in rows]


@skip_no_db
async def test_duplicate_notification_is_queued_once(club: dict[str, int]) -> None:
    first = await _queue(club["club"])
    second = await _queue(club["club"])
    assert first is not None
    assert second is None  # notifications_dedup_uk
    assert len(await _status(club["club"])) == 1


@skip_no_db
async def test_send_pending_marks_sent(
    club: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append({"token": token, "method": method, **payload})
        return {"ok": True}

    monkeypatch.setattr(telegram_api, "call", fake_call)

    await _queue(club["club"])
    sent = await send_pending({})
    assert sent == 1
    assert calls and calls[0]["chat_id"] == CHAT
    assert "Notify Club" in calls[0]["text"]
    assert await _status(club["club"]) == [("SENT", 0)]

    # Ikkinchi yurish hech narsa yubormaydi — idempotent
    assert await send_pending({}) == 0
    assert len(calls) == 1


@skip_no_db
async def test_failed_send_escalates_to_error(
    club: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def dead_call(token: str, method: str, payload: dict[str, Any]) -> None:
        return None  # telegram javob bermadi

    monkeypatch.setattr(telegram_api, "call", dead_call)

    await _queue(club["club"])
    await send_pending({})
    assert await _status(club["club"]) == [("PENDING", 1)]
    await send_pending({})
    assert await _status(club["club"]) == [("PENDING", 2)]
    await send_pending({})
    # MAX_SEND_ATTEMPTS = 3 — endi ERROR, keyingi yurishlar tegmaydi
    assert await _status(club["club"]) == [("ERROR", 3)]
    assert await send_pending({}) == 0
