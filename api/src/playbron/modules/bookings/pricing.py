"""Narx hisobi — sof funksiya, DB'siz.

Manba: `docs/audit-report.md` §2.5 («Tarif yo'q — narx `stations.rate`»).

Klub narxi vaqtga qarab o'zgaradi: kechqurun qimmat, ish kuni arzon,
VIP xona alohida. Buni bitta `stations.rate` ustuni bilan ifodalab
bo'lmaydi.

## Algoritm

1. Bron oynasi tarif chegaralari bo'yicha bo'laklarga bo'linadi.
2. Har bo'lakka MOS keluvchi tariflardan eng yuqori `priority`lisi
   qo'llanadi (tenglikda — eng kichik `id`, ya'ni natija determinlashgan).
3. Bo'lak narxi `price_per_hour * SEKUND` sifatida YIG'ILADI va bo'lish
   FAQAT oxirida bir marta bajariladi. Har bo'lakda alohida bo'linsa
   yaxlitlash xatosi to'planardi.

   Sekund — daqiqa emas: bron `starts_at` sekundli bo'ladi (mijoz
   "hozirdan 3 soatdan keyin" deb yuborsa `:37.512` ham keladi). Daqiqada
   hisoblansa har bo'lak PASTGA yaxlitlanardi va yarim tunni kesib
   o'tgan 2 soatlik bron 120 emas, 119 daqiqa bo'lib to'lanardi —
   klubning har bunday bronida bir daqiqalik yo'qotish.
4. Birorta bo'lakka tarif topilmasa — `NoTariffForSlot`.

## Vaqt

Hamma hisob klubning O'Z zonasidagi devor soatida. Funksiya zona bilan
ishlamaydi: chaqiruvchi allaqachon mahalliy `datetime` beradi
(`CLAUDE.md`, «Vaqt»).

Yarim tundan o'tuvchi tarif (masalan 22:00–02:00) `to_min > 1440` bilan
ifodalanadi va `days_mask` uning BOSHLANGAN kuniga tegishli.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = 3600

# Dushanba = 0-bit ... Yakshanba = 6-bit (`datetime.weekday()` bilan bir xil)
ALL_DAYS = 0b111_1111


class NoTariffForSlot(Exception):
    """Oyna ichidagi biror bo'lakka mos tarif yo'q."""

    def __init__(self, at: datetime) -> None:
        super().__init__(f"Tarif topilmadi: {at.isoformat()}")
        self.at = at


@dataclass(frozen=True, slots=True)
class Tariff:
    """`tariffs` qatorining hisob uchun kerakli qismi."""

    id: int
    days_mask: int
    from_min: int
    to_min: int
    price_per_hour: int
    priority: int
    console_type: str | None = None
    """`None` — har qanday konsolga."""
    room_kind: str | None = None
    """`None` — har qanday xonaga."""


def _midnight(day_date: datetime) -> datetime:
    return day_date.replace(hour=0, minute=0, second=0, microsecond=0)


def _applies_at(tariff: Tariff, moment: datetime) -> bool:
    """Tarif shu lahzada kuchdami.

    Ikki kun qaraladi: lahzaning O'Z kuni va bir kun oldingisi — ikkinchisi
    yarim tundan o'tgan tarif uchun (`to_min > 1440`).
    """
    for day_offset in (0, -1):
        day = _midnight(moment) + timedelta(days=day_offset)
        if not tariff.days_mask & (1 << day.weekday()):
            continue
        rel = int((moment - day).total_seconds() // 60)
        if tariff.from_min <= rel < tariff.to_min:
            return True
    return False


def _pick(
    tariffs: list[Tariff], moment: datetime, *, console_type: str | None, room_kind: str | None
) -> Tariff | None:
    candidates = [
        t
        for t in tariffs
        # `None` — cheklovsiz: har qanday konsol / xona.
        if t.console_type in (None, console_type)
        and t.room_kind in (None, room_kind)
        and _applies_at(t, moment)
    ]
    if not candidates:
        return None
    # Eng yuqori `priority`, tenglikda eng kichik `id` — natija tasodifga
    # bog'liq bo'lmasligi uchun.
    return max(candidates, key=lambda t: (t.priority, -t.id))


def _boundaries(tariffs: list[Tariff], start: datetime, end: datetime) -> list[datetime]:
    """Oyna ichidagi barcha narx o'zgarishi nuqtalari."""
    points = {start, end}
    day = _midnight(start) - timedelta(days=1)
    last = _midnight(end)
    while day <= last:
        points.add(day)
        for tariff in tariffs:
            points.add(day + timedelta(minutes=tariff.from_min))
            points.add(day + timedelta(minutes=tariff.to_min))
        day += timedelta(days=1)
    return sorted(p for p in points if start <= p <= end)


def price_for_window(
    start_local: datetime,
    hours: int,
    tariffs: list[Tariff],
    *,
    console_type: str | None = None,
    room_kind: str | None = None,
) -> int:
    """Bron oynasining to'liq narxi (so'm, butun son).

    `tariffs` bo'sh bo'lsa `NoTariffForSlot` — chaqiruvchi bu holatda
    `stations.rate` ga qaytadi (tarifsiz klublar ishlashda davom etsin).
    """
    if hours <= 0:
        raise ValueError("hours musbat bo'lsin")

    # Oyna DAQIQAGACHA qirqiladi. `starts_at` mijozdan sekund va
    # mikrosekund bilan keladi ("hozirdan 3 soatdan keyin"), tarif
    # chegaralari esa doim butun daqiqada. Qirqilmasa har chegara bo'lagi
    # kasrli bo'lib, yig'indi to'liq oynadan bir necha sekundga kam
    # chiqardi — ya'ni bir xil bron kun davomida turli summa berardi.
    start_local = start_local.replace(second=0, microsecond=0)
    end_local = start_local + timedelta(hours=hours)
    points = _boundaries(tariffs, start_local, end_local)

    # `price_per_hour * sekund` yig'indisi — bo'lish oxirida, bir marta.
    weighted = 0
    for left, right in zip(points, points[1:], strict=False):
        seconds = int((right - left).total_seconds())
        if seconds <= 0:
            continue
        midpoint = left + (right - left) / 2
        tariff = _pick(tariffs, midpoint, console_type=console_type, room_kind=room_kind)
        if tariff is None:
            raise NoTariffForSlot(left)
        weighted += tariff.price_per_hour * seconds

    # Yaxlitlash — eng yaqin so'mga. Float ishlatilmaydi.
    return (weighted + SECONDS_PER_HOUR // 2) // SECONDS_PER_HOUR
