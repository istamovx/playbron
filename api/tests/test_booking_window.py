"""Ish vaqti oynasi — sof funksiya, DB'siz.

`fits_opening_hours()` bron butunlay klubning ish oynasiga sig'ishini
tekshiradi. Ilgari bu filtr FAQAT mijoz brauzerida edi
(`apps/miniapp/src/lib/slots.ts`), ya'ni API'ga to'g'ridan-to'g'ri
murojaat qilib klub yopiq vaqtga bron qilish mumkin edi
(`docs/audit-report.md` §2.4).

Bu fayl `RUN_DB_TESTS` ga BOG'LIQ EMAS va PostgreSQL/Redis talab qilmaydi —
`.env` (yoki CI'dagi kabi muhit o'zgaruvchilari) yetarli.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from playbron.modules.bookings.service import fits_opening_hours

TZ = "Asia/Tashkent"  # UTC+5, DST yo'q

# 10:00–24:00
DAY_OPEN, DAY_CLOSE = 600, 1440
# 10:00–02:00 (`clubs` sukut qiymati) — klub kuni yarim tundan o'tadi
NIGHT_OPEN, NIGHT_CLOSE = 600, 1560


def _tashkent(hour: int, minute: int = 0) -> datetime:
    """Toshkentda `hour:minute` bo'lgan lahzani UTC'da qaytaradi.

    Funksiyaga UTC beriladi — u kirishni server zonasidan emas, aynan
    `timezone` parametridan talqin qilishi kerak.
    """
    return datetime(2026, 8, 20, hour, minute, tzinfo=ZoneInfo(TZ)).astimezone(UTC)


def test_booking_inside_day_window_fits() -> None:
    assert fits_opening_hours(
        _tashkent(20), 2, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone=TZ
    )


def test_booking_ending_exactly_at_closing_fits() -> None:
    assert fits_opening_hours(
        _tashkent(22), 2, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone=TZ
    )


def test_booking_crossing_closing_time_is_rejected() -> None:
    assert not fits_opening_hours(
        _tashkent(23), 2, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone=TZ
    )


def test_booking_before_opening_is_rejected() -> None:
    assert not fits_opening_hours(
        _tashkent(9), 1, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone=TZ
    )


def test_after_midnight_booking_fits_previous_day_window() -> None:
    """01:00–02:00 — kalendar kuni yangi, klub kuni esa kechagi."""
    assert fits_opening_hours(
        _tashkent(1), 1, opens_at_min=NIGHT_OPEN, closes_at_min=NIGHT_CLOSE, timezone=TZ
    )


def test_after_midnight_booking_past_closing_is_rejected() -> None:
    """01:00–03:00 — klub 02:00 da yopiladi."""
    assert not fits_opening_hours(
        _tashkent(1), 2, opens_at_min=NIGHT_OPEN, closes_at_min=NIGHT_CLOSE, timezone=TZ
    )


def test_booking_crossing_midnight_fits_when_club_works_late() -> None:
    """23:00–01:00 — yarim tundan o'tadi, lekin oyna 02:00 gacha."""
    assert fits_opening_hours(
        _tashkent(23), 2, opens_at_min=NIGHT_OPEN, closes_at_min=NIGHT_CLOSE, timezone=TZ
    )


def test_round_the_clock_club_accepts_any_time() -> None:
    """`closes - opens >= 1440` — 24/7 klub, oyna tekshirilmaydi.

    Bu shartsiz `opens=0, closes=1440` bo'lgan klubda yarim tundan
    o'tuvchi bron (23:00+2h) rad etilardi.
    """
    for hour in (0, 3, 11, 23):
        assert fits_opening_hours(
            _tashkent(hour), 6, opens_at_min=0, closes_at_min=1440, timezone=TZ
        ), f"{hour}:00 da rad etildi"


def test_same_instant_differs_by_club_timezone() -> None:
    """Bir xil lahza — Toshkentda 11:00, Londonda 07:00 (BST).

    Klub zonasi almashsa natija ham almashadi: hisob `clubs.timezone`
    orqali ketayotganining isboti, server zonasi orqali emas.
    """
    moment = _tashkent(11)
    assert fits_opening_hours(
        moment, 2, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone=TZ
    )
    assert not fits_opening_hours(
        moment, 2, opens_at_min=DAY_OPEN, closes_at_min=DAY_CLOSE, timezone="Europe/London"
    )
