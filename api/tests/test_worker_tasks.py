"""B3 fon vazifalari — jonli DB bilan.

    docker compose up -d postgres redis
    RUN_DB_TESTS=1 pytest tests/test_worker_tasks.py
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from conftest import purge_audit_actor, rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import context as request_context
from playbron.core import queue
from playbron.core.config import settings
from playbron.core.db import AppSession, session_scope
from playbron.modules.finance import shifts as shifts_service
from playbron.worker import tasks
from playbron.worker.base import club_scope, mark_job_writer
from playbron.worker.tasks import (
    booking_reminders,
    daily_summary,
    expire_unpaid_bookings,
    notify_shift_variance,
)

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

OWNER_CHAT = 777_001
CUSTOMER_TG = 888_001
RATE = 40_000


@pytest_asyncio.fixture
async def world() -> AsyncIterator[dict[str, int]]:
    """Ega (chat bilan), mijoz, klub, stansiya — B3 vazifalarining sahnasi."""
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    ids: dict[str, int] = {}
    async with engine.begin() as conn:
        async with rls_bypass(
            conn,
            "users",
            "organizations",
            "clubs",
            "memberships",
            "staff_telegram",
            "stations",
        ):
            ids["owner"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'wtasks.owner', 'active', 'Ega')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                )
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_telegram (user_id, telegram_id, chat_id)"
                    " VALUES (:u, :t, :c) ON CONFLICT (user_id) DO UPDATE SET chat_id = :c"
                ),
                {"u": ids["owner"], "t": OWNER_CHAT, "c": OWNER_CHAT},
            )
            ids["customer"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, telegram_id, first_name)"
                    " VALUES ('customer', :t, 'Mijoz')"
                    " ON CONFLICT (telegram_id) WHERE kind = 'customer'"
                    " DO UPDATE SET first_name = 'Mijoz' RETURNING id"
                ),
                {"t": CUSTOMER_TG},
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status)"
                    " VALUES (:u, 'WTasks Org', 'active') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'WTasks Club', 'active') RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role)"
                    " VALUES (:u, :c, 'OWNER')"
                    " ON CONFLICT (user_id, club_id) DO UPDATE SET status = 'active'"
                ),
                {"u": ids["owner"], "c": ids["club"]},
            )
            ids["station"] = await conn.scalar(
                text(
                    "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                    " VALUES (:c, 'WT-1', 'Standart', 'ps5', :r) RETURNING id"
                ),
                {"c": ids["club"], "r": RATE},
            )
    yield ids
    async with engine.begin() as conn:
        async with rls_bypass(
            conn,
            "users",
            "organizations",
            "notifications",
            "jobs",
            "bookings",
            "shifts",
            "stations",
            "staff_telegram",
        ):
            await purge_audit_actor(conn, ids["owner"])
            for table in ("notifications", "jobs", "bookings", "shifts", "stations"):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE club_id = :c"),  # noqa: S608
                    {"c": ids["club"]},
                )
            await conn.execute(
                text("DELETE FROM staff_telegram WHERE user_id = :u"), {"u": ids["owner"]}
            )
            await conn.execute(
                text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]}
            )
            await conn.execute(
                text(
                    "DELETE FROM users WHERE (login = 'wtasks.owner' AND kind = 'staff')"
                    " OR (telegram_id = :t AND kind = 'customer')"
                ),
                {"t": CUSTOMER_TG},
            )
    await engine.dispose()


async def _insert_booking(
    world: dict[str, int],
    *,
    status: str,
    starts_in_min: int,
    created_ago_min: int = 0,
) -> int:
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    starts = datetime.now(UTC) + timedelta(minutes=starts_in_min)
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            booking_id = await conn.scalar(
                text(
                    "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                    " period, hours, rate_snapshot, console_type, created_at)"
                    " VALUES (:c, :s, :cust, 'MINIAPP', :status,"
                    " tstzrange(:starts, :ends), 1, :rate, 'ps5',"
                    " now() - make_interval(mins => :ago)) RETURNING id"
                ),
                {
                    "c": world["club"],
                    "s": world["station"],
                    "cust": world["customer"],
                    "status": status,
                    "starts": starts,
                    "ends": starts + timedelta(hours=1),
                    "rate": RATE,
                    "ago": created_ago_min,
                },
            )
    await engine.dispose()
    return int(booking_id)


async def _booking_status(booking_id: int, world: dict[str, int]) -> tuple[str, str | None]:
    async with club_scope(world["club"]) as session:
        row = (
            await session.execute(
                text("SELECT status, cancel_reason FROM bookings WHERE id = :id"),
                {"id": booking_id},
            )
        ).one()
    return row.status, row.cancel_reason


async def _notifications(world: dict[str, int]) -> list[Any]:
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            return list(
                (
                    await session.execute(
                        text(
                            "SELECT template, chat_id, entity_id, status FROM notifications"
                            " WHERE club_id = :c ORDER BY id"
                        ),
                        {"c": world["club"]},
                    )
                ).all()
            )


@skip_no_db
async def test_expire_cancels_only_stale_pending(world: dict[str, int]) -> None:
    stale = await _insert_booking(world, status="PENDING", starts_in_min=180, created_ago_min=30)
    fresh = await _insert_booking(world, status="PENDING", starts_in_min=240, created_ago_min=2)
    confirmed = await _insert_booking(
        world, status="CONFIRMED", starts_in_min=300, created_ago_min=60
    )

    await expire_unpaid_bookings({})

    assert await _booking_status(stale, world) == ("CANCELLED", "PAYMENT_WINDOW_EXPIRED")
    assert (await _booking_status(fresh, world))[0] == "PENDING"
    assert (await _booking_status(confirmed, world))[0] == "CONFIRMED"

    # Idempotent: ikkinchi yurish hech narsani o'zgartirmaydi
    await expire_unpaid_bookings({})
    assert await _booking_status(stale, world) == ("CANCELLED", "PAYMENT_WINDOW_EXPIRED")
    assert (await _booking_status(fresh, world))[0] == "PENDING"


@skip_no_db
async def test_reminders_queue_correct_stage_once(world: dict[str, int]) -> None:
    soon = await _insert_booking(world, status="CONFIRMED", starts_in_min=15)
    early = await _insert_booking(world, status="CONFIRMED", starts_in_min=90)

    await booking_reminders({})
    rows = await _notifications(world)
    by_entity = {int(r.entity_id): r.template for r in rows}
    assert by_entity[soon] == "booking_reminder_20m"
    assert by_entity[early] == "booking_reminder_2h"
    assert all(int(r.chat_id) == CUSTOMER_TG for r in rows)

    # Dedup: qayta yurish yangi qator qo'shmaydi
    await booking_reminders({})
    assert len(await _notifications(world)) == 2


@skip_no_db
async def test_daily_summary_goes_to_owner_once(
    world: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Toshkent 09:30 — xulosa oynasi ochiq
    frozen = datetime(2026, 8, 20, 4, 30, tzinfo=UTC)
    monkeypatch.setattr(tasks, "_now", lambda: frozen)

    await daily_summary({})
    rows = [r for r in await _notifications(world) if r.template == "daily_summary"]
    assert len(rows) == 1
    assert int(rows[0].chat_id) == OWNER_CHAT
    assert int(rows[0].entity_id) == 20_260_819  # kechagi sana

    await daily_summary({})
    rows = [r for r in await _notifications(world) if r.template == "daily_summary"]
    assert len(rows) == 1  # dedup


@skip_no_db
async def test_variance_alert_enqueued_and_delivered(
    world: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    async with engine.begin() as conn:
        async with rls_bypass(conn, "shifts"):
            shift_id = await conn.scalar(
                text(
                    "INSERT INTO shifts (club_id, staff_id, opening_cash)"
                    " VALUES (:c, :s, 0) RETURNING id"
                ),
                {"c": world["club"], "s": world["owner"]},
            )
    await engine.dispose()

    captured: list[tuple[str, tuple[Any, ...]]] = []

    async def fake_enqueue(job: str, *args: Any, **kwargs: Any) -> bool:
        captured.append((job, args))
        return True

    monkeypatch.setattr(queue, "enqueue", fake_enqueue)

    # Kutilgan naqd 0, sanalgan 100 000 — farq limitdan katta.
    # Yopish — API yo'li: HAQIQIY aktyor konteksti (worker claim'i emas),
    # chunki shifts policy'lari rolni memberships'dan tekshiradi.
    request_context.set_context(
        request_context.RequestContext(
            user_id=world["owner"],
            club_id=world["club"],
            roles={world["club"]: "OWNER"},
        )
    )
    try:
        async with session_scope() as session:
            detail = await shifts_service.close_shift(
                session,
                club_id=world["club"],
                shift_id=int(shift_id),
                counted_cash=100_000,
                closed_by=world["owner"],
            )
    finally:
        request_context.reset()
    assert detail["variance"] == 100_000
    assert captured and captured[0][0] == "notify_shift_variance"
    _, args = captured[0]
    assert args[0] == world["club"] and args[1] == int(shift_id)
    assert args[2]["variance"] == 100_000

    # Worker vazifasi bildirishnomani egaga navbatlaydi
    queued = await notify_shift_variance({}, world["club"], int(shift_id), args[2])
    assert queued == 1
    rows = [r for r in await _notifications(world) if r.template == "shift_variance"]
    assert len(rows) == 1 and int(rows[0].chat_id) == OWNER_CHAT
