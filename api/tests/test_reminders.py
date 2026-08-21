"""Bron eslatmasi — da'vo (claim) va yuborish.

Manba: `api/migrations/versions/0038_booking_reminders.py`.

Eng muhim invariant: eslatma BIR MARTA ketadi. Da'vo `UPDATE ...
RETURNING` bilan atomar bo'lgani uchun ikkinchi chaqiruv bo'sh qaytishi
shart — aks holda mijoz har daqiqada bir xil xabarni olardi.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from conftest import purge_audit_actor, rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import db as core_db
from playbron.core.config import settings
from playbron.modules.bookings import reminders

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

OWNER_LOGIN = "rem.owner"
CUSTOMER_TG = 980_000_444
RATE = 40_000


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture
async def world() -> AsyncIterator[dict[str, int]]:
    """Mijozi Telegram'ga ulangan, 10 daqiqadan keyin boshlanadigan bron."""
    engine = _owner_engine()
    ids: dict[str, int] = {}

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "stations", "bookings", "rooms"
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
            ids["customer"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, telegram_id, status, first_name)"
                    " VALUES ('customer', :tg, 'active', 'Mijoz')"
                    " ON CONFLICT (telegram_id) WHERE kind = 'customer'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"tg": CUSTOMER_TG},
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'Rem Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status, opens_at_min, closes_at_min)"
                    " VALUES (:o, 'Cyber Arena', 'active', 0, 1440) RETURNING id"
                ),
                {"o": ids["org"]},
            )
            ids["room"] = await conn.scalar(
                text("INSERT INTO rooms (club_id, name, kind) VALUES (:c, '1-xona', 'Standart')"
                     " RETURNING id"),
                {"c": ids["club"]},
            )
            ids["station"] = await conn.scalar(
                text(
                    "INSERT INTO stations (club_id, code, room_label, room_id, console_type, rate)"
                    " VALUES (:c, 'REM-1', '1-xona', :r, 'ps5', :rate) RETURNING id"
                ),
                {"c": ids["club"], "r": ids["room"], "rate": RATE},
            )
            starts = datetime.now(UTC) + timedelta(minutes=10)
            ids["booking"] = await conn.scalar(
                text(
                    "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                    " period, hours, rate_snapshot, play_amount, console_type)"
                    " VALUES (:c, :s, :u, 'MINIAPP', 'CONFIRMED',"
                    " tstzrange(:starts, :ends), 3, :rate, :play, 'ps5') RETURNING id"
                ),
                {
                    "c": ids["club"],
                    "s": ids["station"],
                    "u": ids["customer"],
                    "starts": starts,
                    "ends": starts + timedelta(hours=3),
                    "rate": RATE,
                    "play": RATE * 3,
                },
            )

    await core_db.dispose()
    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "bookings", "rooms"):
            await purge_audit_actor(conn, ids["owner"], ids["customer"])
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [ids["owner"], ids["customer"]]},
            )
    await engine.dispose()


@skip_no_db
async def test_reminder_is_sent_once_and_only_once(
    world: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[int, str]] = []

    async def fake_send(token: str, chat_id: int, body: str) -> None:  # noqa: ARG001
        sent.append((chat_id, body))

    monkeypatch.setattr(reminders.telegram_api, "send_message", fake_send)

    assert await reminders.send_due_reminders() >= 1
    assert any(chat == CUSTOMER_TG for chat, _ in sent)

    body = next(b for chat, b in sent if chat == CUSTOMER_TG)
    assert "Cyber Arena" in body
    assert "🎮 Xona: 1-xona" in body
    assert "⏳ Vaqt: 3 soat" in body

    # Ikkinchi aylanish — da'vo allaqachon qo'yilgan, takror YO'Q
    before = len(sent)
    await reminders.send_due_reminders()
    assert len(sent) == before, "bir xil bron uchun eslatma ikki marta ketdi"


@skip_no_db
async def test_far_future_booking_is_not_reminded_yet(
    world: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Yetakchi oynadan tashqaridagi bron hali tegilmaydi."""
    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            far = datetime.now(UTC) + timedelta(hours=5)
            await conn.execute(
                text(
                    "UPDATE bookings SET period = tstzrange(:s, :e), reminder_sent_at = NULL"
                    " WHERE id = :id"
                ),
                {"s": far, "e": far + timedelta(hours=3), "id": world["booking"]},
            )
    await core_db.dispose()
    await engine.dispose()

    sent: list[int] = []

    async def fake_send(token: str, chat_id: int, body: str) -> None:  # noqa: ARG001
        sent.append(chat_id)

    monkeypatch.setattr(reminders.telegram_api, "send_message", fake_send)

    await reminders.send_due_reminders()
    assert CUSTOMER_TG not in sent
