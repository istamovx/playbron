"""Fon vazifalari vaqt hisob-kitoblari — DB'SIZ, `RUN_DB_TESTS`siz o'tadi.

    cd api && python -m pytest tests/test_worker_pure.py -q

Kutilgan qiymatlar qo'lda hisoblangan (Asia/Tashkent = UTC+5, DST yo'q).
"""

from datetime import UTC, date, datetime

from playbron.worker.schedule import (
    date_key,
    local_day_utc_range,
    local_hhmm,
    reminder_template,
    summary_date,
)

TASHKENT = "Asia/Tashkent"


# ── reminder_template ─────────────────────────────────────────────────────


def test_started_booking_gets_no_reminder() -> None:
    assert reminder_template(0) is None
    assert reminder_template(-5) is None


def test_soon_window_wins_over_early() -> None:
    # 15 daqiqa qolganda «20 daqiqa» shabloni — «2 soat» emas
    assert reminder_template(15) == "booking_reminder_20m"
    assert reminder_template(20) == "booking_reminder_20m"


def test_early_window_boundaries() -> None:
    assert reminder_template(20.5) == "booking_reminder_2h"
    assert reminder_template(120) == "booking_reminder_2h"
    assert reminder_template(121) is None


# ── local_hhmm ────────────────────────────────────────────────────────────


def test_local_hhmm_shifts_to_club_zone() -> None:
    # 13:30 UTC = 18:30 Toshkent
    moment = datetime(2026, 8, 20, 13, 30, tzinfo=UTC)
    assert local_hhmm(moment, TASHKENT) == "18:30"


# ── summary_date ──────────────────────────────────────────────────────────


def test_summary_fires_at_club_nine_oclock() -> None:
    # 04:30 UTC = 09:30 Toshkent → kechagi sana
    now = datetime(2026, 8, 20, 4, 30, tzinfo=UTC)
    assert summary_date(now, TASHKENT) == date(2026, 8, 19)


def test_summary_quiet_before_nine() -> None:
    # 03:59 UTC = 08:59 Toshkent
    now = datetime(2026, 8, 20, 3, 59, tzinfo=UTC)
    assert summary_date(now, TASHKENT) is None


def test_summary_quiet_after_ten() -> None:
    # 05:00 UTC = 10:00 Toshkent — soat oynasi yopilgan
    now = datetime(2026, 8, 20, 5, 0, tzinfo=UTC)
    assert summary_date(now, TASHKENT) is None


def test_summary_respects_other_zones() -> None:
    # 13:00 UTC = 09:00 EDT (Nyu-York, avgustda UTC-4) → kechagi sana
    now = datetime(2026, 8, 20, 13, 0, tzinfo=UTC)
    assert summary_date(now, "America/New_York") == date(2026, 8, 19)
    # O'sha lahza Toshkentda 18:00 — jim
    assert summary_date(now, TASHKENT) is None


# ── date_key / local_day_utc_range ────────────────────────────────────────


def test_date_key_format() -> None:
    assert date_key(date(2026, 8, 20)) == 20_260_820
    assert date_key(date(2026, 1, 5)) == 20_260_105


def test_local_day_utc_range_tashkent() -> None:
    # Toshkent 2026-08-20 kuni = UTC 19-avgust 19:00 dan 20-avgust 19:00 gacha
    start, end = local_day_utc_range(date(2026, 8, 20), TASHKENT)
    assert start == datetime(2026, 8, 19, 19, 0, tzinfo=UTC)
    assert end == datetime(2026, 8, 20, 19, 0, tzinfo=UTC)
