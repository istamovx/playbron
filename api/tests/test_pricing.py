"""Narx kalkulyatori — sof funksiya, DB'siz va PostgreSQL'siz.

`CLAUDE.md`, «Testlar»: sof hisob funksiyasi DB'siz test bilan qoplanadi.
Bu fayl `RUN_DB_TESTS` ga bog'liq emas.
"""

from dataclasses import replace
from datetime import datetime

import pytest

from playbron.modules.bookings.pricing import (
    ALL_DAYS,
    NoTariffForSlot,
    Tariff,
    price_for_window,
)

# 2026-08-17 — DUSHANBA (weekday 0). Barcha sinovlar shu haftadan.
MONDAY = datetime(2026, 8, 17, 0, 0)
SATURDAY = datetime(2026, 8, 22, 0, 0)

WEEKDAYS = 0b001_1111  # Du–Ju
WEEKEND = 0b110_0000  # Sha–Ya


def at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute)


BASE = Tariff(
    id=1,
    days_mask=ALL_DAYS,
    from_min=0,
    to_min=24 * 60,
    price_per_hour=40_000,
    priority=0,
)


def base(**over: object) -> Tariff:
    """`BASE` ning nusxasi, ko'rsatilgan maydonlari almashtirilgan."""
    return replace(BASE, **over)  # type: ignore[arg-type]


def test_single_flat_tariff() -> None:
    assert price_for_window(at(MONDAY, 12), 2, [base()]) == 80_000


def test_interval_is_split_at_tariff_boundary() -> None:
    """18:00 dan narx oshadi — 17:00–19:00 broni IKKI bo'lakka bo'linadi."""
    day = base(id=1, from_min=0, to_min=18 * 60, price_per_hour=40_000)
    evening = base(id=2, from_min=18 * 60, to_min=24 * 60, price_per_hour=60_000)

    assert price_for_window(at(MONDAY, 17), 2, [day, evening]) == 40_000 + 60_000


def test_higher_priority_wins_over_overlapping_tariff() -> None:
    """Umumiy tarif va uning ustidagi aksiya — aksiya yutadi."""
    general = base(id=1, price_per_hour=40_000, priority=0)
    happy_hour = base(
        id=2, from_min=14 * 60, to_min=16 * 60, price_per_hour=20_000, priority=10
    )

    # 13:00–17:00: 1 soat umumiy + 2 soat aksiya + 1 soat umumiy
    assert price_for_window(at(MONDAY, 13), 4, [general, happy_hour]) == (
        40_000 + 20_000 + 20_000 + 40_000
    )


def test_ties_are_resolved_by_lowest_id_not_by_input_order() -> None:
    first = base(id=7, price_per_hour=50_000, priority=5)
    second = base(id=3, price_per_hour=30_000, priority=5)

    assert price_for_window(at(MONDAY, 12), 1, [first, second]) == 30_000
    assert price_for_window(at(MONDAY, 12), 1, [second, first]) == 30_000


def test_weekday_and_weekend_masks_are_honoured() -> None:
    weekday = base(id=1, days_mask=WEEKDAYS, price_per_hour=40_000)
    weekend = base(id=2, days_mask=WEEKEND, price_per_hour=60_000)
    tariffs = [weekday, weekend]

    assert price_for_window(at(MONDAY, 12), 1, tariffs) == 40_000
    assert price_for_window(at(SATURDAY, 12), 1, tariffs) == 60_000


def test_booking_crossing_midnight_switches_day_mask() -> None:
    """23:00–01:00 — birinchi soat dushanba, ikkinchisi seshanba.

    Tarif kunlik niqob bilan berilgani uchun bu ikki BOSHQA narx.
    """
    monday_only = base(id=1, days_mask=0b000_0001, price_per_hour=40_000)
    tuesday_only = base(id=2, days_mask=0b000_0010, price_per_hour=60_000)

    assert price_for_window(at(MONDAY, 23), 2, [monday_only, tuesday_only]) == 100_000


def test_overnight_tariff_belongs_to_its_starting_day() -> None:
    """22:00–02:00 tarifi dushanba niqobi bilan seshanba 01:00 ni ham qoplaydi."""
    night = base(
        id=1,
        days_mask=0b000_0001,  # faqat dushanba
        from_min=22 * 60,
        to_min=26 * 60,  # 02:00 (ertasi kun)
        price_per_hour=30_000,
    )

    assert price_for_window(at(MONDAY, 23), 2, [night]) == 60_000


def test_missing_tariff_for_any_part_is_rejected() -> None:
    """Kechqurun tarifi yo'q — 17:00–19:00 broni QISMAN narxlanmaydi."""
    day_only = base(from_min=0, to_min=18 * 60)

    with pytest.raises(NoTariffForSlot):
        price_for_window(at(MONDAY, 17), 2, [day_only])


def test_no_tariffs_at_all_is_rejected() -> None:
    with pytest.raises(NoTariffForSlot):
        price_for_window(at(MONDAY, 12), 1, [])


def test_console_and_room_targets_narrow_the_match() -> None:
    generic = base(id=1, price_per_hour=40_000, priority=0)
    ps5_vip = base(id=2, price_per_hour=90_000, priority=5, console_type="ps5", room_kind="VIP")

    assert price_for_window(at(MONDAY, 12), 1, [generic, ps5_vip]) == 40_000
    assert (
        price_for_window(
            at(MONDAY, 12), 1, [generic, ps5_vip], console_type="ps5", room_kind="VIP"
        )
        == 90_000
    )
    # Konsol mos, xona mos emas — maxsus tarif QO'LLANMAYDI
    assert (
        price_for_window(
            at(MONDAY, 12), 1, [generic, ps5_vip], console_type="ps5", room_kind="Standart"
        )
        == 40_000
    )


def test_half_hour_start_rounds_once_not_per_segment() -> None:
    """Yarim soatlik chegara + toq narx — yaxlitlash BIR MARTA.

    Har bo'lakda alohida bo'linsa 12 500 + 17 500 = 30 000 chiqardi;
    to'g'ri javob (25 000*30 + 35 000*30)/60 = 30 000 — bu misolda mos,
    lekin toq qiymatda farq qiladi: quyidagi 33 333 uni ko'rsatadi.
    """
    early = base(id=1, from_min=0, to_min=13 * 60, price_per_hour=33_333)
    late = base(id=2, from_min=13 * 60, to_min=24 * 60, price_per_hour=33_333)

    # 12:30–13:30 — ikki bo'lak, jami roppa-rosa bir soat
    assert price_for_window(at(MONDAY, 12, 30), 1, [early, late]) == 33_333


def test_zero_or_negative_hours_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        price_for_window(at(MONDAY, 12), 0, [base()])


def test_a_start_with_seconds_is_priced_as_a_whole_window() -> None:
    """Sekundli boshlanish oynani KAMAYTIRMAYDI.

    Mijoz "hozirdan uch soatdan keyin" deb yuborsa `starts_at` sekund va
    mikrosekund bilan keladi. Chegarani kesib o'tgan oynada har bo'lak
    alohida pastga yaxlitlanardi: 2 soatlik bron 119 daqiqa bo'lib
    to'lanardi va bir xil bron kunning qaysi sekundida yuborilganiga
    qarab TURLI summa berardi.
    """
    tariff = base(id=1, from_min=0, to_min=24 * 60, price_per_hour=55_000)
    exact = at(MONDAY, 22)
    ragged = exact.replace(second=37, microsecond=512_000)

    # 22:00 dan boshlangan 2 soat yarim tunni kesib o'tadi
    assert price_for_window(exact, 2, [tariff]) == 110_000
    assert price_for_window(ragged, 2, [tariff]) == 110_000


def test_boundary_crossing_keeps_every_minute_paid() -> None:
    """Ikki tarif orasidagi chegarada birorta daqiqa yo'qolmaydi."""
    early = base(id=1, from_min=0, to_min=23 * 60, price_per_hour=40_000)
    late = base(id=2, from_min=23 * 60, to_min=24 * 60, price_per_hour=60_000)

    # 22:00–24:00 — 60 daqiqa arzon, 60 daqiqa qimmat
    start = at(MONDAY, 22).replace(second=41, microsecond=7)
    assert price_for_window(start, 2, [early, late]) == 100_000
