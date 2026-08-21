"""Fon vazifalarining vaqt hisob-kitoblari — sof, DB'siz.

Hammasi `clubs.timezone` asosida; server zonasiga tayanish YO'Q
(CLAUDE.md §Vaqt). Testlar: `tests/test_worker_pure.py`
(`RUN_DB_TESTS`siz o'tadi).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

REMINDER_SOON_MIN = 20
REMINDER_EARLY_MIN = 120
SUMMARY_HOUR = 9


def reminder_template(minutes_left: float) -> str | None:
    """Boshlanishiga qolgan daqiqaga ko'ra eslatma shabloni.

    Eng yaqin bosqich ustun: 15 daqiqa qolganda «2 soat» emas,
    «20 daqiqa» yuboriladi. Boshlanib bo'lgan yoki hali uzoq — None.
    """
    if minutes_left <= 0:
        return None
    if minutes_left <= REMINDER_SOON_MIN:
        return "booking_reminder_20m"
    if minutes_left <= REMINDER_EARLY_MIN:
        return "booking_reminder_2h"
    return None


def local_hhmm(moment: datetime, timezone: str) -> str:
    """UTC lahzani klub vaqtida HH:MM ko'rinishida beradi."""
    return moment.astimezone(ZoneInfo(timezone)).strftime("%H:%M")


def summary_date(now: datetime, timezone: str) -> date | None:
    """Kunlik xulosa vaqti keldimi — kelgan bo'lsa KECHAGI sana.

    Klub vaqti bilan soat 09 da (istalgan daqiqada — worker to'xtab
    qolsa ham soat oxirigacha ulgurish uchun; takror yuborishni dedup
    to'xtatadi).
    """
    local = now.astimezone(ZoneInfo(timezone))
    if local.hour != SUMMARY_HOUR:
        return None
    return local.date() - timedelta(days=1)


def date_key(day: date) -> int:
    """Sana → 20260820 ko'rinishidagi butun son (dedup `entity_id`)."""
    return day.year * 10_000 + day.month * 100 + day.day


def local_day_utc_range(day: date, timezone: str) -> tuple[datetime, datetime]:
    """Klub vaqtidagi bitta kunning UTC chegaralari [boshi, oxiri)."""
    tz = ZoneInfo(timezone)
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)
