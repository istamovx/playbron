"""Bron biznes mantig'i — validatsiya + yozish. RLS defense-in-depth,
bu yerdagi tekshiruvlar HAKAM (`docs/05-auth-redesign.md` uslubi bilan bir xil).
"""

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.audit import log_action
from playbron.core.errors import PG_UNIQUE_VIOLATION, AppError, Forbidden, NotFound
from playbron.core.text import clean_name
from playbron.modules.bookings import notify, pricing
from playbron.modules.bot.contact import normalize_phone

# `bookings_hours_range_ck` (`0009_bookings.py`) DB'da qo'ygan yuqori chegara.
# Uzaytirish shu qiymatdan oshsa CHECK buziladi — servis buni oldindan
# ushlaydi, aks holda foydalanuvchi 500 ko'radi.
MAX_TOTAL_HOURS = 12
# Bron boshlanishidan necha daqiqa oldin hali ham qabul qilinadi (soat
# ustida turgan foydalanuvchi "hozir" ni bir necha soniya kech bosishi mumkin)
PAST_GRACE_MIN = 2
MINUTES_PER_DAY = 24 * 60


def _station_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "room_label": row.room_label,
        "console_type": row.console_type,
        "rate": int(row.rate),
        "status": row.status,
    }


_PUBLISH_ERRORS = {
    "NOT_AUTHENTICATED": ("Avval kiring", "NOT_AUTHENTICATED"),
    "NOT_ALLOWED": ("Bu amal uchun ruxsat yo'q", "ROLE_FORBIDDEN"),
    "NOT_FOUND": ("Klub topilmadi", "CLUB_NOT_FOUND"),
    "ALREADY_ACTIVE": ("Klub allaqachon faol", "CLUB_ALREADY_ACTIVE"),
    "NO_STATIONS": ("Kamida bitta faol xona qo'shing", "CLUB_NO_STATIONS"),
}


async def publish_club(session: AsyncSession, *, club_id: int) -> None:
    """Klub egasi/admini `draft` klubni o'zi faollashtiradi (`0012_club_publish.py`).

    Super admin tasdig'i SHART EMAS — bu `organizations.status` (tarif)
    bilan ARALASHTIRILMAYDI, u alohida o'q.
    """
    result = await session.scalar(text("SELECT club_publish(:c)"), {"c": club_id})
    if result != "OK":
        message, code = _PUBLISH_ERRORS.get(
            str(result), ("Faollashtirib bo'lmadi", "PUBLISH_FAILED")
        )
        raise AppError(message, code=code, status_code=409 if code != "ROLE_FORBIDDEN" else 403)


async def list_active_clubs(session: AsyncSession) -> list[dict[str, Any]]:
    """Mijoz ilovasidagi klub katalogi — `clubs_read` (`0001`) status='active'ni
    tokensiz ochadi, boshqa GUC kerak emas."""
    rows = (
        await session.execute(
            text(
                "SELECT id, name, address, phone, about, cover_url,"
                "       opens_at_min, closes_at_min, timezone,"
                "       min_booking_hours, max_booking_hours, max_advance_days,"
                "       slot_step_min,"
                "       google_maps_url, yandex_maps_url"
                " FROM clubs WHERE status = 'active' ORDER BY name"
            )
        )
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "address": r.address,
            "phone": r.phone,
            "about": r.about,
            "cover_url": r.cover_url,
            "opens_at_min": r.opens_at_min,
            "closes_at_min": r.closes_at_min,
            "timezone": r.timezone,
            "min_booking_hours": r.min_booking_hours,
            "max_booking_hours": r.max_booking_hours,
            "max_advance_days": r.max_advance_days,
            "slot_step_min": r.slot_step_min,
            "google_maps_url": r.google_maps_url,
            "yandex_maps_url": r.yandex_maps_url,
        }
        for r in rows
    ]


async def get_club_for_staff(session: AsyncSession, club_id: int) -> dict[str, Any] | None:
    """Xodim/egasi o'z klubini `status`i (shu jumladan `draft`) bilan ko'radi.

    `list_active_clubs()`dan farqi — u faqat `active`ni qaytaradi, ya'ni
    hali nashr qilinmagan klub egasiga ham UMUMAN ko'rinmas edi. `clubs_read`
    (`0001`) o'z a'zoligi orqali `draft`ni ham ochadi.
    """
    row = (
        await session.execute(
            text(
                "SELECT id, name, address, phone, about, cover_url,"
                "       opens_at_min, closes_at_min, timezone, status,"
                "       min_booking_hours, max_booking_hours, max_advance_days,"
                "       slot_step_min, extend_max_hours,"
                "       google_maps_url, yandex_maps_url"
                " FROM clubs WHERE id = :id"
            ),
            {"id": club_id},
        )
    ).first()
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "address": row.address,
        "phone": row.phone,
        "about": row.about,
        "cover_url": row.cover_url,
        "opens_at_min": row.opens_at_min,
        "closes_at_min": row.closes_at_min,
        "timezone": row.timezone,
        "status": row.status,
        "min_booking_hours": row.min_booking_hours,
        "max_booking_hours": row.max_booking_hours,
        "max_advance_days": row.max_advance_days,
        "slot_step_min": row.slot_step_min,
        "extend_max_hours": row.extend_max_hours,
        "google_maps_url": row.google_maps_url,
        "yandex_maps_url": row.yandex_maps_url,
    }


async def list_stations(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT id, code, room_label, console_type, rate, status"
                " FROM stations WHERE club_id = :club_id AND status = 'active'"
                " ORDER BY rate, code"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_station_row_to_dict(r) for r in rows]


async def list_all_stations(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Boshqaruv uchun — `maintenance` xonalar ham, faqat `active` emas."""
    rows = (
        await session.execute(
            text(
                "SELECT id, code, room_label, console_type, rate, status"
                " FROM stations WHERE club_id = :club_id ORDER BY code"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_station_row_to_dict(r) for r in rows]


CONSOLE_TYPES = ("ps3", "ps4", "ps4pro", "ps5", "ps5pro")


async def create_station(
    session: AsyncSession,
    *,
    club_id: int,
    code: str,
    room_label: str,
    rate: int,
) -> dict[str, Any]:
    """Konsol turi endi xonaga biriktirilmaydi (reja #38, loyiha egasi,
    2026-08-16) — `console_type` yangi xonalarda `NULL`, bron/hisob
    ochilganda tanlanadi (`_resolve_console_type()`)."""
    if rate <= 0:
        raise AppError("Narx musbat bo'lsin", code="RATE_INVALID")

    code = code.strip()
    if not code:
        raise AppError("Xona kodini kiriting", code="CODE_REQUIRED")

    room_id = await _resolve_room_id(session, club_id, room_label)

    try:
        station_id = await session.scalar(
            text(
                "INSERT INTO stations (club_id, code, room_label, room_id, rate, status)"
                " VALUES (:club_id, :code, :room_label, :room_id, :rate, 'active')"
                " RETURNING id"
            ),
            {
                "club_id": club_id,
                "code": code,
                "room_label": room_label.strip() or "Standart",
                "room_id": room_id,
                "rate": rate,
            },
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == PG_UNIQUE_VIOLATION:
            raise AppError("Bu kod bilan xona allaqachon bor", code="STATION_CODE_TAKEN") from exc
        raise

    await log_action(
        action="station_created",
        target=code,
        club_id=club_id,
        after={"code": code, "room_label": room_label, "rate": rate},
    )

    return {
        "id": station_id,
        "code": code,
        "room_label": room_label.strip() or "Standart",
        "console_type": None,
        "rate": rate,
        "status": "active",
    }


async def _resolve_room_id(session: AsyncSession, club_id: int, room_label: str) -> int:
    """`stations.room_label` matni -> `rooms` qatori, kerak bo'lsa yaratiladi.

    `0033` `rooms` jadvalini qo'shdi va MAVJUD stansiyalarni unga bog'ladi,
    lekin `room_id` ni YOZADIGAN kod yo'q edi: migratsiyadan keyin
    yaratilgan har bir stansiyada `room_id IS NULL` qolardi. Oqibati
    jimgina va qimmat — `pricing._pick()` xonaga bog'langan tarifni
    (`tariffs.room_kind`) `room_kind IS NULL` bo'lgani uchun rad etardi:
    VIP xona umumiy narxda hisoblanardi, klubda faqat xonaga bog'langan
    tarif bo'lsa esa har bir bron `NO_TARIFF_FOR_SLOT` bilan yiqilardi.

    Tur (`kind`) sukut bilan nomning o'zi — `0033` backfill'i ham shunday
    qilgan; keyin egasi Narxlar ekranidan o'zgartiradi.
    """
    name = room_label.strip() or "Standart"
    row = (
        await session.execute(
            text(
                "INSERT INTO rooms (club_id, name, kind) VALUES (:club_id, :name, :name)"
                " ON CONFLICT (club_id, name) DO UPDATE SET name = EXCLUDED.name"
                " RETURNING id"
            ),
            {"club_id": club_id, "name": name},
        )
    ).first()
    if row is None:  # amalda yuz bermaydi — `DO UPDATE` doim qator qaytaradi
        raise NotFound("Xona turi topilmadi")
    return int(row.id)


async def update_station(
    session: AsyncSession,
    *,
    club_id: int,
    station_id: int,
    room_label: str,
    rate: int,
    status: str,
) -> dict[str, Any]:
    if rate <= 0:
        raise AppError("Narx musbat bo'lsin", code="RATE_INVALID")
    if status not in ("active", "maintenance"):
        raise AppError("Noma'lum holat", code="STATUS_INVALID")

    room_id = await _resolve_room_id(session, club_id, room_label)

    row = (
        await session.execute(
            text(
                "UPDATE stations SET room_label = :room_label, room_id = :room_id,"
                " rate = :rate, status = :status"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id, code, room_label, console_type, rate, status"
            ),
            {
                "room_label": room_label.strip() or "Standart",
                "room_id": room_id,
                "rate": rate,
                "status": status,
                "id": station_id,
                "club_id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Xona topilmadi")

    await log_action(
        action="station_updated",
        target=row.code,
        club_id=club_id,
        after={"room_label": room_label, "rate": rate, "status": status},
    )

    return _station_row_to_dict(row)


# ── Xonalar va tariflar ───────────────────────────────────────────────────
# Jadval, RLS va konstreyntlar `0037_rooms_tariffs.py` da. `0033` ularni
# ochib qo'ygan, lekin BOSHQARUV yo'li qolmagan edi: tarifni faqat xom SQL
# bilan kiritish mumkin edi (`CLAUDE.md`, «Ma'lum texnik qarz»). Quyidagi
# CRUD o'sha bo'shliqni yopadi.
#
# O'CHIRISH ATAYLAB YO'Q: yopilgan bronning narxi shu qatorlar orqali
# hisoblangan va `pricing.py` ularga qarab ishlaydi — `products` naqshi
# bilan `is_active = false` qilinadi.

ROOM_NAME_MAX = 64
ROOM_KIND_MAX = 32
ROOM_KIND_DEFAULT = "Standart"
TARIFF_NAME_MAX = 64
# `tariffs_days_mask_ck` — dushanba 1-bit ... yakshanba 64-bit
# (`pricing.ALL_DAYS` bilan bir xil qiymat, `datetime.weekday()` tartibi).
DAYS_MASK_ALL = pricing.ALL_DAYS
# `tariffs_window_ck` — `to_min` yarim tundan o'tishi mumkin (22:00–02:00
# → 1320..1560), shuning uchun yuqori chegara ikki sutka.
TARIFF_MAX_TO_MIN = 2 * MINUTES_PER_DAY


def _room_row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "sort": row.sort,
        "is_active": row.is_active,
    }


def _clean_room_fields(name: str, kind: str) -> tuple[str, str]:
    clean = clean_name(name, limit=ROOM_NAME_MAX)
    if not clean:
        raise AppError("Xona nomini kiriting", code="ROOM_NAME_REQUIRED")
    return clean, clean_name(kind, limit=ROOM_KIND_MAX) or ROOM_KIND_DEFAULT


async def list_rooms(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Boshqaruv ro'yxati — nofaol xonalar ham (tarif ularga hali havola qiladi)."""
    rows = (
        await session.execute(
            text(
                "SELECT id, name, kind, sort, is_active FROM rooms"
                " WHERE club_id = :club_id ORDER BY sort, name"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_room_row(r) for r in rows]


async def create_room(
    session: AsyncSession, *, club_id: int, name: str, kind: str, sort: int
) -> dict[str, Any]:
    name, kind = _clean_room_fields(name, kind)
    try:
        room_id = await session.scalar(
            text(
                "INSERT INTO rooms (club_id, name, kind, sort)"
                " VALUES (:club_id, :name, :kind, :sort) RETURNING id"
            ),
            {"club_id": club_id, "name": name, "kind": kind, "sort": sort},
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == PG_UNIQUE_VIOLATION:
            raise AppError("Bu nomli xona allaqachon bor", code="ROOM_NAME_TAKEN") from exc
        raise

    await log_action(
        action="room_created",
        target=name,
        club_id=club_id,
        after={"name": name, "kind": kind, "sort": sort},
    )
    return {"id": room_id, "name": name, "kind": kind, "sort": sort, "is_active": True}


async def update_room(
    session: AsyncSession,
    *,
    club_id: int,
    room_id: int,
    name: str,
    kind: str,
    sort: int,
    is_active: bool,
) -> dict[str, Any]:
    name, kind = _clean_room_fields(name, kind)
    try:
        row = (
            await session.execute(
                text(
                    "UPDATE rooms SET name = :name, kind = :kind, sort = :sort,"
                    "                 is_active = :is_active"
                    " WHERE id = :id AND club_id = :club_id"
                    " RETURNING id, name, kind, sort, is_active"
                ),
                {
                    "name": name,
                    "kind": kind,
                    "sort": sort,
                    "is_active": is_active,
                    "id": room_id,
                    "club_id": club_id,
                },
            )
        ).first()
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == PG_UNIQUE_VIOLATION:
            raise AppError("Bu nomli xona allaqachon bor", code="ROOM_NAME_TAKEN") from exc
        raise
    if row is None:
        raise NotFound("Xona topilmadi")

    await log_action(
        action="room_updated",
        target=name,
        club_id=club_id,
        after={"name": name, "kind": kind, "sort": sort, "is_active": is_active},
    )
    return _room_row(row)


def _tariff_row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "days_mask": row.days_mask,
        "from_min": row.from_min,
        "to_min": row.to_min,
        "price_per_hour": int(row.price_per_hour),
        "priority": row.priority,
        "console_type": row.console_type,
        "room_kind": row.room_kind,
        "is_active": row.is_active,
    }


def _clean_tariff_fields(
    *,
    name: str,
    days_mask: int,
    from_min: int,
    to_min: int,
    price_per_hour: int,
    console_type: str | None,
    room_kind: str | None,
) -> dict[str, Any]:
    """`0033` dagi CHECK'larning ilova tomonidagi nusxasi.

    Bu yerda YANGI biznes qoidasi yo'q — har bir shart aynan
    `tariffs_price_positive_ck`, `tariffs_days_mask_ck` va
    `tariffs_window_ck` dan olingan. Maqsad tushunarli xabar berish:
    konstreyntning o'zi ishlab ketsa foydalanuvchi `CONSTRAINT_VIOLATED`
    ko'rardi va nimani tuzatishni bilmasdi.

    Kesishgan tariflar ATAYLAB taqiqlanmaydi — `pricing.py` ularni
    `priority` bo'yicha hal qiladi, ya'ni kesishish modelning O'ZIDA bor.
    """
    clean = clean_name(name, limit=TARIFF_NAME_MAX)
    if not clean:
        raise AppError("Tarif nomini kiriting", code="TARIFF_NAME_REQUIRED")
    if price_per_hour <= 0:
        raise AppError("Narx musbat bo'lsin", code="PRICE_INVALID")
    if not 1 <= days_mask <= DAYS_MASK_ALL:
        raise AppError("Kamida bitta kun tanlansin", code="DAYS_MASK_INVALID")
    if not 0 <= from_min < MINUTES_PER_DAY:
        raise AppError("Boshlanish vaqti bir sutka ichida bo'lsin", code="TARIFF_WINDOW_INVALID")
    if not from_min < to_min <= TARIFF_MAX_TO_MIN:
        raise AppError("Tugash vaqti boshlanishdan keyin bo'lsin", code="TARIFF_WINDOW_INVALID")
    if console_type is not None and console_type not in CONSOLE_TYPES:
        raise AppError("Noma'lum konsol turi", code="CONSOLE_TYPE_INVALID")

    # Bo'sh qator `NULL` ga tenglashtiriladi — `0033`: `NULL` «har qanday
    # xonaga» degani, bo'sh matnli xona turi esa yo'q.
    return {"name": clean, "room_kind": clean_name(room_kind, limit=ROOM_KIND_MAX) or None}


async def list_tariffs(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Boshqaruv ro'yxati — nofaollar ham. Narx hisobi `_load_tariffs()` da,
    u faqat `is_active` qatorlarni oladi."""
    rows = (
        await session.execute(
            text(
                "SELECT id, name, days_mask, from_min, to_min, price_per_hour, priority,"
                "       console_type, room_kind, is_active"
                " FROM tariffs WHERE club_id = :club_id"
                " ORDER BY priority DESC, from_min, id"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_tariff_row(r) for r in rows]


async def create_tariff(
    session: AsyncSession,
    *,
    club_id: int,
    name: str,
    days_mask: int,
    from_min: int,
    to_min: int,
    price_per_hour: int,
    priority: int,
    console_type: str | None,
    room_kind: str | None,
) -> dict[str, Any]:
    cleaned = _clean_tariff_fields(
        name=name,
        days_mask=days_mask,
        from_min=from_min,
        to_min=to_min,
        price_per_hour=price_per_hour,
        console_type=console_type,
        room_kind=room_kind,
    )
    fields: dict[str, Any] = {
        "name": cleaned["name"],
        "days_mask": days_mask,
        "from_min": from_min,
        "to_min": to_min,
        "price_per_hour": price_per_hour,
        "priority": priority,
        "console_type": console_type,
        "room_kind": cleaned["room_kind"],
    }
    tariff_id = await session.scalar(
        text(
            "INSERT INTO tariffs (club_id, name, days_mask, from_min, to_min,"
            "                     price_per_hour, priority, console_type, room_kind)"
            " VALUES (:club_id, :name, :days_mask, :from_min, :to_min,"
            "         :price_per_hour, :priority, :console_type, :room_kind)"
            " RETURNING id"
        ),
        {"club_id": club_id, **fields},
    )

    await log_action(
        action="tariff_created",
        target=cleaned["name"],
        club_id=club_id,
        after=fields,
    )
    return {"id": tariff_id, "is_active": True, **fields}


async def update_tariff(
    session: AsyncSession,
    *,
    club_id: int,
    tariff_id: int,
    name: str,
    days_mask: int,
    from_min: int,
    to_min: int,
    price_per_hour: int,
    priority: int,
    console_type: str | None,
    room_kind: str | None,
    is_active: bool,
) -> dict[str, Any]:
    cleaned = _clean_tariff_fields(
        name=name,
        days_mask=days_mask,
        from_min=from_min,
        to_min=to_min,
        price_per_hour=price_per_hour,
        console_type=console_type,
        room_kind=room_kind,
    )
    fields: dict[str, Any] = {
        "name": cleaned["name"],
        "days_mask": days_mask,
        "from_min": from_min,
        "to_min": to_min,
        "price_per_hour": price_per_hour,
        "priority": priority,
        "console_type": console_type,
        "room_kind": cleaned["room_kind"],
        "is_active": is_active,
    }
    row = (
        await session.execute(
            text(
                "UPDATE tariffs SET name = :name, days_mask = :days_mask,"
                "                   from_min = :from_min, to_min = :to_min,"
                "                   price_per_hour = :price_per_hour, priority = :priority,"
                "                   console_type = :console_type, room_kind = :room_kind,"
                "                   is_active = :is_active"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id, name, days_mask, from_min, to_min, price_per_hour,"
                "           priority, console_type, room_kind, is_active"
            ),
            {"id": tariff_id, "club_id": club_id, **fields},
        )
    ).first()
    if row is None:
        raise NotFound("Tarif topilmadi")

    await log_action(
        action="tariff_updated",
        target=cleaned["name"],
        club_id=club_id,
        after=fields,
    )
    return _tariff_row(row)


def _clean_maps_url(value: str | None, *, field_label: str) -> str | None:
    """Bo'sh qatorni `NULL`ga tenglaydi, aks holda `https://` shart —
    havola keyin BOSHQA foydalanuvchi (mijoz) tomonidan ochiladi, shuning
    uchun `javascript:`/`data:` kabi sxemalar bu yerda kesib tashlanadi
    (DB'dagi `clubs_google_maps_url_https_ck`/`..._yandex_..._ck` — ikkinchi
    qatlam, `0014_club_maps_links.py`)."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not cleaned.startswith("https://"):
        raise AppError(
            f"{field_label} havolasi https:// bilan boshlanishi kerak", code="MAPS_URL_INVALID"
        )
    return cleaned


async def update_club(
    session: AsyncSession,
    *,
    club_id: int,
    name: str,
    address: str,
    phone: str | None,
    about: str,
    opens_at_min: int,
    closes_at_min: int,
    min_booking_hours: int,
    max_booking_hours: int,
    max_advance_days: int,
    extend_max_hours: int,
    slot_step_min: int,
    google_maps_url: str | None = None,
    yandex_maps_url: str | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise AppError("Klub nomini kiriting", code="NAME_REQUIRED")
    if not (0 <= opens_at_min < closes_at_min <= 1560):
        raise AppError(
            "Ish vaqti noto'g'ri — yopilish ochilishdan keyin, 26:00 (1560) gacha",
            code="HOURS_INVALID",
        )
    # `0033` ustunlarni qo'shdi, lekin ularni YOZADIGAN yo'l yo'q edi:
    # konstantalar shunchaki koddan bazaga ko'chirilgan, har bir tenant
    # esa 1/6/14/3/30 ga abadiy mixlangan edi.
    if not min_booking_hours <= max_booking_hours:
        raise AppError(
            "Eng kam davomiylik eng ko'pdan oshmasin", code="BOOKING_HOURS_INVALID"
        )
    google_maps_url = _clean_maps_url(google_maps_url, field_label="Google Maps")
    yandex_maps_url = _clean_maps_url(yandex_maps_url, field_label="Yandex Maps")

    row = (
        await session.execute(
            text(
                "UPDATE clubs SET name = :name, address = :address, phone = :phone,"
                " about = :about, opens_at_min = :opens_at_min, closes_at_min = :closes_at_min,"
                " min_booking_hours = :min_booking_hours,"
                " max_booking_hours = :max_booking_hours,"
                " max_advance_days = :max_advance_days,"
                " extend_max_hours = :extend_max_hours,"
                " slot_step_min = :slot_step_min,"
                " google_maps_url = :google_maps_url, yandex_maps_url = :yandex_maps_url"
                " WHERE id = :id"
                " RETURNING id, name, address, phone, about, cover_url,"
                "           opens_at_min, closes_at_min, timezone,"
                "           min_booking_hours, max_booking_hours, max_advance_days,"
                "           extend_max_hours, slot_step_min,"
                "           google_maps_url, yandex_maps_url"
            ),
            {
                "name": name.strip(),
                "address": address.strip(),
                "phone": phone.strip() if phone else None,
                "about": about.strip(),
                "opens_at_min": opens_at_min,
                "closes_at_min": closes_at_min,
                "min_booking_hours": min_booking_hours,
                "max_booking_hours": max_booking_hours,
                "max_advance_days": max_advance_days,
                "extend_max_hours": extend_max_hours,
                "slot_step_min": slot_step_min,
                "google_maps_url": google_maps_url,
                "yandex_maps_url": yandex_maps_url,
                "id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Klub topilmadi")

    await log_action(
        action="club_updated",
        target=row.name,
        club_id=club_id,
        after={
            "name": row.name,
            "address": row.address,
            "opens_at_min": row.opens_at_min,
            "closes_at_min": row.closes_at_min,
        },
    )

    return {
        "id": row.id,
        "name": row.name,
        "address": row.address,
        "phone": row.phone,
        "about": row.about,
        "cover_url": row.cover_url,
        "opens_at_min": row.opens_at_min,
        "closes_at_min": row.closes_at_min,
        "timezone": row.timezone,
        "min_booking_hours": row.min_booking_hours,
        "max_booking_hours": row.max_booking_hours,
        "max_advance_days": row.max_advance_days,
        "extend_max_hours": row.extend_max_hours,
        "slot_step_min": row.slot_step_min,
        "google_maps_url": row.google_maps_url,
        "yandex_maps_url": row.yandex_maps_url,
    }


async def _club_timezone(session: AsyncSession, club_id: int) -> str:
    tz = await session.scalar(text("SELECT timezone FROM clubs WHERE id = :id"), {"id": club_id})
    return str(tz) if tz else "Asia/Tashkent"


def _local_day_window(local_date: Any, timezone: str) -> tuple[datetime, datetime]:
    """`date` (yil-oy-kun, vaqt zonasisiz) — klubning O'Z vaqt zonasidagi
    kun boshi/oxiri, timestamptz solishtirish uchun.

    Avval `day.replace(hour=0, ...)` — NAIVE datetime edi. asyncpg naive
    qiymatni `timestamptz`ga kodlaganda JARAYON (konteyner) OS vaqt
    zonasidan foydalanadi (`.astimezone()`), bu odatda UTC — klub
    vaqt zonasi (`Asia/Tashkent`, UTC+5) EMAS. Natija: kun oynasi 5 soat
    siljigan, ba'zi bronlar noto'g'ri kunga tushib qolgan — mijoz bo'sh
    deb ko'rgan slot aslida band bo'lib, `409 SLOT_TAKEN` chiqqan
    (loyiha egasi, 2026-08-16: "mijoz sifatida bron qilolmadim, vaqt
    tanlangan deydi"). `notify.py::format_starts_at()`dagi bilan bir xil
    naqsh — `ZoneInfo(timezone)`.
    """
    day_start = datetime.combine(local_date, time.min, tzinfo=ZoneInfo(timezone))
    return day_start, day_start + timedelta(days=1)


async def list_day_bookings(
    session: AsyncSession, club_id: int, day: datetime
) -> list[dict[str, Any]]:
    """Berilgan kunning FAOL (PENDING/CONFIRMED) bronlari — bo'sh slot hisoblash uchun.

    Frontend `freeStations` mantig'ini o'zgartirmasin deb, xom band oraliqlar
    qaytariladi — bo'sh slotni hisoblash mijoz tomonida qoladi.
    """
    timezone = await _club_timezone(session, club_id)
    day_start, day_end = _local_day_window(day.date(), timezone)

    rows = (
        await session.execute(
            text(
                "SELECT station_id, lower(period) AS starts_at, upper(period) AS ends_at, status"
                " FROM bookings"
                " WHERE club_id = :club_id AND status IN ('PENDING', 'CONFIRMED')"
                "   AND period && tstzrange(:day_start, :day_end)"
                " ORDER BY station_id, starts_at"
            ),
            {"club_id": club_id, "day_start": day_start, "day_end": day_end},
        )
    ).all()
    return [
        {
            "station_id": r.station_id,
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "status": r.status,
        }
        for r in rows
    ]


async def list_timeline(
    session: AsyncSession, club_id: int, day: datetime
) -> list[dict[str, Any]]:
    """Kunlik jadval — har stansiya, shu kundagi barcha bron, mehmon ismi
    va stansiya ma'lumoti bilan boyitilgan.

    `list_day_bookings()`dan FARQI: bu yerda faqat xom oraliq emas, to'liq
    ko'rsatish ma'lumoti qaytadi (`timeline.tsx` — xodim ekrani). Bekor
    qilingan (`CANCELLED`) bronlar chiqarib tashlanadi — ular hech qachon
    sodir bo'lmagan, jadvalda ko'rsatishning ma'nosi yo'q.
    """
    timezone = await _club_timezone(session, club_id)
    day_start, day_end = _local_day_window(day.date(), timezone)

    rows = (
        await session.execute(
            text(
                "SELECT b.id, b.station_id, s.code AS station_code, s.room_label,"
                # Xonadan emas, BRONdan — konsol endi shu darajada tanlanadi (reja #38)
                "       b.console_type, lower(b.period) AS starts_at,"
                "       upper(b.period) AS ends_at, b.status, b.closed_at IS NOT NULL AS closed,"
                "       COALESCE(b.guest_name, u.display_name, u.first_name) AS guest_label"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE b.club_id = :club_id AND b.status <> 'CANCELLED'"
                "   AND b.period && tstzrange(:day_start, :day_end)"
                " ORDER BY s.code, starts_at"
            ),
            {"club_id": club_id, "day_start": day_start, "day_end": day_end},
        )
    ).all()
    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "station_code": r.station_code,
            "room_label": r.room_label,
            "console_type": r.console_type,
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "status": r.status,
            "closed": bool(r.closed),
            "guest_label": r.guest_label,
        }
        for r in rows
    ]


async def _load_club_and_station(
    session: AsyncSession, club_id: int, station_id: int
) -> tuple[Any, Any]:
    # Klub va stansiya BITTA so'rovda — ikkalasi ham har bron/narx
    # chaqiruvida kerak va ular bitta AsyncSession'da parallel ketolmaydi,
    # ya'ni ikkinchi so'rov sof qo'shimcha kechikish edi
    # (`finance/reports.py::_club_report_context` bilan bir xil tuzatish).
    row = (
        await session.execute(
            text(
                "SELECT c.id AS club_id, c.name AS club_name, c.timezone, c.status AS club_status,"
                "       c.opens_at_min, c.closes_at_min, c.max_advance_days,"
                "       c.min_booking_hours, c.max_booking_hours,"
                "       s.id AS station_id, s.code, s.console_type, s.rate,"
                "       s.status AS station_status, r.kind AS room_kind"
                " FROM clubs c"
                " LEFT JOIN stations s ON s.id = :station_id AND s.club_id = c.id"
                " LEFT JOIN rooms r ON r.id = s.room_id"
                " WHERE c.id = :club_id"
            ),
            {"club_id": club_id, "station_id": station_id},
        )
    ).first()

    if row is None or row.club_status != "active":
        raise NotFound("Klub topilmadi")
    if row.station_id is None or row.station_status != "active":
        raise NotFound("Xona topilmadi")

    # Chaqiruvchilar `club.name`/`station.code` kabi nomlarni kutadi —
    # bitta qatorni ikkita ko'rinishga ajratamiz.
    club = SimpleNamespace(
        id=row.club_id,
        name=row.club_name,
        timezone=row.timezone,
        status=row.club_status,
        opens_at_min=row.opens_at_min,
        closes_at_min=row.closes_at_min,
        max_advance_days=row.max_advance_days,
        min_booking_hours=row.min_booking_hours,
        max_booking_hours=row.max_booking_hours,
    )
    station = SimpleNamespace(
        id=row.station_id,
        code=row.code,
        console_type=row.console_type,
        rate=row.rate,
        status=row.station_status,
        room_kind=row.room_kind,
    )
    return club, station


def _resolve_console_type(console_type: str | None, station: Any) -> str:
    """Reja #38 (loyiha egasi, 2026-08-16) — konsol turi endi bron/hisob
    ochilganda tanlanadi, xonaga biriktirilmaydi. Orqaga moslik: eski
    (0023'dan oldingi) xonalar hali `console_type`ga ega — u berilmasa
    SUKUT sifatida ishlatiladi (mini-app hali yangilanmagan yo'llar
    buzilmasin). Konsolsiz (yangi) xonada esa bu endi MAJBURIY."""
    if console_type is not None:
        if console_type not in CONSOLE_TYPES:
            raise AppError("Noma'lum konsol turi", code="CONSOLE_TYPE_INVALID")
        return console_type
    if station.console_type is not None:
        return str(station.console_type)
    raise AppError("Konsol turini tanlang", code="CONSOLE_TYPE_REQUIRED")


def fits_opening_hours(
    starts_at: datetime, hours: int, *, opens_at_min: int, closes_at_min: int, timezone: str
) -> bool:
    """Bron butunlay klubning ish oynasiga sig'adimi.

    Sof funksiya — DB'siz test qilinadi (`tests/test_booking_window.py`).

    `closes_at_min` 1440 dan katta bo'lishi mumkin (`clubs` sukut qiymati
    1560 = ertalabki 02:00), ya'ni klub kuni yarim tundan o'tadi. Shu sababli
    ikkita oyna qaraladi: bron BOSHLANGAN kalendar kuniniki va bir kun
    OLDINGISI (o'sha kunning tungi davomi). Bittasiga to'liq sig'sa — yetarli.

    Hisob klubning O'Z zonasidagi devor soatida (`clubs.timezone`), server
    yoki brauzer zonasida emas (`CLAUDE.md`, «Vaqt»).
    """
    # 24/7 klub — oyna butun sutkani qoplaydi, tekshiradigan narsa yo'q.
    # Bu shart bo'lmasa `opens=0, closes=1440` bo'lgan klubda ham yarim
    # tundan o'tuvchi bron rad etilardi.
    if closes_at_min - opens_at_min >= MINUTES_PER_DAY:
        return True

    zone = ZoneInfo(timezone)
    local_start = starts_at.astimezone(zone)
    # Tugash HAQIQIY lahzadan olinadi, `start + hours*60` devor soatidan
    # EMAS. DST bo'lgan zonada (funksiya `clubs.timezone`ni parametr
    # sifatida oladi — ya'ni Toshkent bilan chegaralanmagan) o'tish
    # kechasi bu ikkisi bir soatga farq qiladi.
    local_end = (starts_at + timedelta(hours=hours)).astimezone(zone)

    # DEVOR soati bo'yicha: ikki aware datetime AYIRMASI haqiqiy o'tgan
    # vaqtni beradi (ya'ni doim `hours`), oyna esa mahalliy soatga qarab
    # tekshiriladi. Shuning uchun tugash mahalliy sana+soatdan quriladi.
    start_min = local_start.hour * 60 + local_start.minute
    day_shift = (local_end.date() - local_start.date()).days
    end_min = day_shift * MINUTES_PER_DAY + local_end.hour * 60 + local_end.minute

    for day_offset in (0, -1):
        window_start = opens_at_min + day_offset * MINUTES_PER_DAY
        window_end = closes_at_min + day_offset * MINUTES_PER_DAY
        if window_start <= start_min and end_min <= window_end:
            return True
    return False


def _assert_within_opening_hours(club: Any, starts_at: datetime, hours: int) -> None:
    if fits_opening_hours(
        starts_at,
        hours,
        opens_at_min=int(club.opens_at_min),
        closes_at_min=int(club.closes_at_min),
        timezone=club.timezone,
    ):
        return
    raise AppError(
        "Bron klubning ish vaqtidan tashqarida", code="OUTSIDE_OPENING_HOURS", status_code=422
    )


def _validate_window(starts_at: datetime, hours: int, club: Any) -> datetime:
    """Chegaralar KLUB sozlamasidan (`0037_rooms_tariffs.py`).

    `club` MAJBURIY va ustunlar `NOT NULL DEFAULT` — shuning uchun bu yerda
    zaxira konstanta YO'Q. Bo'lsa edi, SELECT'dan ustun tushib qolganda
    tenant sozlamasi jimgina e'tiborsiz qolardi va hech narsa yiqilmasdi
    (`docs/HOLAT.md` §4.1 dagi "jimgina 0 qator" saboqning aynan o'zi).
    """
    min_hours = int(club.min_booking_hours)
    max_hours = int(club.max_booking_hours)
    advance_days = int(club.max_advance_days)

    if not (min_hours <= hours <= max_hours):
        raise AppError(
            f"Davomiylik {min_hours}–{max_hours} soat oralig'ida bo'lsin",
            code="HOURS_OUT_OF_RANGE",
        )

    if starts_at.tzinfo is None:
        raise AppError("Vaqt zona bilan berilishi kerak", code="STARTS_AT_INVALID")

    now = datetime.now(UTC)
    if starts_at < now - timedelta(minutes=PAST_GRACE_MIN):
        raise AppError("O'tib ketgan vaqtga bron qilib bo'lmaydi", code="STARTS_AT_PAST")

    if starts_at > now + timedelta(days=advance_days):
        raise AppError(
            f"Bron faqat {advance_days} kun oldinga qilinadi", code="STARTS_AT_TOO_FAR"
        )

    return starts_at


async def _load_tariffs(session: AsyncSession, club_id: int) -> list[pricing.Tariff]:
    rows = (
        await session.execute(
            text(
                "SELECT id, days_mask, from_min, to_min, price_per_hour, priority,"
                "       console_type, room_kind"
                " FROM tariffs WHERE club_id = :club_id AND is_active"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        pricing.Tariff(
            id=r.id,
            days_mask=r.days_mask,
            from_min=r.from_min,
            to_min=r.to_min,
            price_per_hour=int(r.price_per_hour),
            priority=r.priority,
            console_type=r.console_type,
            room_kind=r.room_kind,
        )
        for r in rows
    ]


async def quote_play_amount(
    session: AsyncSession,
    *,
    club: Any,
    station: Any,
    starts_at: datetime,
    hours: int,
    console_type: str,
) -> tuple[int, int]:
    """Bron oynasining to'liq narxi va ko'rsatish uchun soatlik qiymat.

    Tarif YO'Q bo'lsa `stations.rate` ga qaytadi — tarif jadvalini hali
    to'ldirmagan klublar ishlashda davom etsin (`0033` gacha butun narx
    modeli shu ustun edi).

    Tarif bor, lekin oynaning bir qismini qoplamasa — bu KLUB SOZLAMASIDAGI
    kamchilik, jimgina `stations.rate` ga tushib ketilmaydi: xodim buni
    ko'rib tuzatishi kerak.
    """
    tariffs = await _load_tariffs(session, int(club.id))
    if not tariffs:
        total = int(station.rate) * hours
    else:
        local_start = starts_at.astimezone(ZoneInfo(club.timezone))
        try:
            total = pricing.price_for_window(
                local_start.replace(tzinfo=None),
                hours,
                tariffs,
                console_type=console_type,
                room_kind=getattr(station, "room_kind", None),
            )
        except pricing.NoTariffForSlot as exc:
            raise AppError(
                "Bu vaqt uchun tarif belgilanmagan", code="NO_TARIFF_FOR_SLOT", status_code=422
            ) from exc

    # Ikkinchi qiymat — faqat KO'RSATISH uchun o'rtacha soatlik narx.
    # Tarif oyna ichida o'zgarsa `rate * hours != total` bo'ladi, shuning
    # uchun hisob-kitob hamma joyda `play_amount` bo'yicha ketadi.
    return total, total // hours


async def quote_booking(
    session: AsyncSession,
    *,
    club_id: int,
    station_id: int,
    starts_at: datetime,
    hours: int,
    console_type: str | None = None,
) -> dict[str, Any]:
    """Bron qilinmasdan narxni hisoblab beradi.

    Bron YARATMAYDI va hech narsani band qilmaydi — shuning uchun
    to'qnashuv tekshirilmaydi. Validatsiya `create_customer_booking()`
    bilan BIR XIL: mijoz "narxi shu" degan javobni olib, keyin bron
    bosganda boshqa xatoga uchramasin.
    """
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours, club)
    _assert_within_opening_hours(club, starts_at, hours)
    resolved_console = _resolve_console_type(console_type, station)

    play_amount, rate = await quote_play_amount(
        session,
        club=club,
        station=station,
        starts_at=starts_at,
        hours=hours,
        console_type=resolved_console,
    )
    return {
        "play_amount": play_amount,
        "rate_snapshot": rate,
        "hours": hours,
        "console_type": resolved_console,
    }


async def create_customer_booking(
    session: AsyncSession,
    *,
    club_id: int,
    customer_id: int,
    station_id: int,
    starts_at: datetime,
    hours: int,
    console_type: str | None = None,
) -> dict[str, Any]:
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours, club)
    # Faqat MIJOZ yo'lida. Mini App allaqachon shu oynani filtrlaydi
    # (`apps/miniapp/src/lib/slots.ts`), lekin u YAGONA to'siq edi —
    # API'ga to'g'ridan-to'g'ri murojaat qilib klub yopiq vaqtga bron
    # qilish mumkin edi (`docs/audit-report.md` §2.4).
    # Xodim yo'lida ATAYLAB tekshirilmaydi: klubda turgan xodim kech
    # qolgan mijozni yozishi kerak va bu qaror uniki.
    _assert_within_opening_hours(club, starts_at, hours)
    resolved_console = _resolve_console_type(console_type, station)

    ends_at = starts_at + timedelta(hours=hours)
    play_amount, rate = await quote_play_amount(
        session,
        club=club,
        station=station,
        starts_at=starts_at,
        hours=hours,
        console_type=resolved_console,
    )

    booking_id = await session.scalar(
        text(
            "INSERT INTO bookings"
            " (club_id, station_id, customer_id, source, status, period, hours,"
            "  rate_snapshot, play_amount, console_type)"
            " VALUES (:club_id, :station_id, :customer_id, 'MINIAPP', 'PENDING',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate, :play, :console_type)"
            " RETURNING id"
        ),
        {
            "club_id": club_id,
            "station_id": station_id,
            "customer_id": customer_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "hours": hours,
            "rate": rate,
            "play": play_amount,
            "console_type": resolved_console,
        },
    )

    guest = (
        await session.execute(
            text("SELECT display_name, first_name FROM users WHERE id = :uid"),
            {"uid": customer_id},
        )
    ).first()
    guest_label = (guest.display_name or guest.first_name) if guest else "Mijoz"

    # Best-effort — xato bron yaratilishini bekor qilmaydi
    await notify.notify_staff_new_booking(
        session,
        club_id=club_id,
        club_name=club.name,
        station_code=station.code,
        guest_label=guest_label,
        starts_label=notify.format_starts_at(starts_at, club.timezone),
        hours=hours,
    )

    return {
        "id": booking_id,
        "station_id": station_id,
        "status": "PENDING",
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "hours": hours,
        "rate_snapshot": rate,
        "play_amount": play_amount,
        "console_type": resolved_console,
        "prepaid_amount": 0,
    }


async def create_staff_booking(
    session: AsyncSession,
    *,
    club_id: int,
    created_by: int,
    station_id: int,
    starts_at: datetime,
    hours: int,
    guest_name: str,
    guest_phone: str,
    console_type: str | None = None,
) -> dict[str, Any]:
    """Xodim qo'lda ochadi — telefon/kelib bron qilgan mijoz uchun.

    `status='CONFIRMED'` DARHOL: xodimning o'zi tasdiqlovchi, ikkinchi
    bosqich shart emas — "qog'ozbozlikdan qutilish" aynan shu.
    """
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours, club)
    resolved_console = _resolve_console_type(console_type, station)

    name = clean_name(guest_name, limit=128)
    if len(name) < 2:
        raise AppError("Mijoz ismi kamida 2 belgi bo'lsin", code="GUEST_NAME_INVALID")

    phone = normalize_phone(guest_phone)
    if phone is None:
        raise AppError("Telefon raqami +998XXXXXXXXX ko'rinishida bo'lsin", code="PHONE_INVALID")

    ends_at = starts_at + timedelta(hours=hours)
    play_amount, rate = await quote_play_amount(
        session,
        club=club,
        station=station,
        starts_at=starts_at,
        hours=hours,
        console_type=resolved_console,
    )

    booking_id = await session.scalar(
        text(
            "INSERT INTO bookings"
            " (club_id, station_id, guest_name, guest_phone, source, status,"
            "  period, hours, rate_snapshot, play_amount, console_type, created_by,"
            "  confirmed_by, confirmed_at)"
            " VALUES (:club_id, :station_id, :guest_name, :guest_phone, 'STAFF', 'CONFIRMED',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate, :play, :console_type,"
            "         :created_by, :created_by, now())"
            " RETURNING id"
        ),
        {
            "club_id": club_id,
            "station_id": station_id,
            "guest_name": name,
            "guest_phone": phone,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "hours": hours,
            "rate": rate,
            "play": play_amount,
            "console_type": resolved_console,
            "created_by": created_by,
        },
    )

    return {
        "id": booking_id,
        "station_id": station_id,
        "status": "CONFIRMED",
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "hours": hours,
        "rate_snapshot": rate,
        "play_amount": play_amount,
        "console_type": resolved_console,
        "guest_name": name,
        "guest_phone": phone,
    }


async def list_pending_bookings(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT b.id, b.station_id, s.code AS station_code,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       b.hours, b.rate_snapshot, b.play_amount,"
                "       COALESCE(u.display_name, u.first_name) AS customer_name,"
                "       u.phone AS customer_phone"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE b.club_id = :club_id AND b.status = 'PENDING' AND b.source = 'MINIAPP'"
                " ORDER BY lower(b.period)"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "station_code": r.station_code,
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "hours": r.hours,
            "rate_snapshot": int(r.rate_snapshot),
            "play_amount": int(r.play_amount),
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
        }
        for r in rows
    ]


async def _load_pending_booking(session: AsyncSession, club_id: int, booking_id: int) -> Any:
    row = (
        await session.execute(
            text(
                # `u.telegram_id` ATAYLAB SHU YERDA o'qiladi — bron holati
                # o'zgarishidan OLDIN. `users_booking_contact` policy'si
                # (`0009_bookings.py`) mijoz qatorini FAQAT uning shu klubda
                # `PENDING`/`CONFIRMED` broni bo'lsa ochadi. Bron `CANCELLED`
                # bo'lgach bu shart yolg'onga aylanadi va keyingi o'qish
                # jimgina NULL qaytaradi — natijada rad etilgan mijozga xabar
                # UMUMAN bormasdi (audit topilmasi, 2026-08-16;
                # `[[playbron-rls-cross-table-subquery-gap]]` bilan bir xil sinf).
                "SELECT b.id, b.customer_id, b.status, b.source, b.hours,"
                "       lower(b.period) AS starts_at, s.code AS station_code,"
                "       COALESCE(r.name, s.room_label) AS room_label,"
                "       c.name AS club_name, c.timezone AS club_tz,"
                "       u.telegram_id AS customer_telegram_id"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " LEFT JOIN rooms r ON r.id = s.room_id"
                " JOIN clubs c ON c.id = b.club_id"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE b.id = :id AND b.club_id = :club_id"
            ),
            {"id": booking_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Bron topilmadi")
    return row


async def confirm_booking(
    session: AsyncSession, *, club_id: int, booking_id: int, staff_id: int
) -> None:
    booking = await _load_pending_booking(session, club_id, booking_id)
    if booking.status != "PENDING":
        raise Forbidden("Bron allaqachon hal qilingan", code="BOOKING_NOT_PENDING")

    await session.execute(
        text(
            "UPDATE bookings SET status = 'CONFIRMED', confirmed_by = :staff_id,"
            " confirmed_at = now() WHERE id = :id"
        ),
        {"id": booking_id, "staff_id": staff_id},
    )

    if booking.customer_id is not None:
        await notify.notify_customer_confirmed(
            session,
            club_id=club_id,
            customer_id=booking.customer_id,
            club_name=booking.club_name,
            room_label=booking.room_label,
            starts_at=booking.starts_at,
            hours=booking.hours,
            timezone=booking.club_tz,
        )


async def reject_booking(
    session: AsyncSession, *, club_id: int, booking_id: int, staff_id: int, reason: str | None
) -> None:
    booking = await _load_pending_booking(session, club_id, booking_id)
    if booking.status != "PENDING":
        raise Forbidden("Bron allaqachon hal qilingan", code="BOOKING_NOT_PENDING")

    clean_reason = clean_name(reason, limit=300) if reason else None

    await session.execute(
        text(
            "UPDATE bookings SET status = 'CANCELLED', cancelled_by = :staff_id,"
            " cancelled_at = now(), cancel_reason = :reason WHERE id = :id"
        ),
        {"id": booking_id, "staff_id": staff_id, "reason": clean_reason},
    )

    if booking.customer_id is not None:
        await notify.notify_customer_rejected(
            session,
            customer_id=booking.customer_id,
            club_name=booking.club_name,
            reason=clean_reason,
            # UPDATE'dan OLDIN o'qilgan — endi RLS uni ko'rsatmaydi
            telegram_id=booking.customer_telegram_id,
        )


# ── Live Board detali — buyurtma, uzaytirish, bekor qilish ─────────────────
# Reja #36 (loyiha egasi, 2026-08-16): "Live boardda karta tanlansa hisob
# ma'lumotini ko'rish mumkin bo'lsin — buyurtma, ochilgan vaqt, countdown,
# vaqtni uzaytirish"; "mijoz kelmasa xodim bekor qilishi mumkin bo'lsin —
# Live board va Timeline'da".


async def _load_booking_for_staff(session: AsyncSession, club_id: int, booking_id: int) -> Any:
    """`_load_pending_booking()`dan farqli — status cheklovisiz, xodim
    ko'radigan HAR QANDAY bron uchun (detail/uzaytirish/bekor qilish)."""
    row = (
        await session.execute(
            text(
                # `u.telegram_id` — bekor qilishdan OLDIN o'qiladi
                # (`_load_pending_booking()`dagi bilan bir xil sabab:
                # `users_booking_contact` policy'si `CANCELLED`dan keyin
                # mijoz qatorini yopadi).
                # `s.rate`, `r.kind`, `c.extend_max_hours` — uzaytirish
                # narxi uchun. Ilgari `extend_booking()` ular uchun
                # `_load_club_and_station()` ni alohida chaqirardi va o'sha
                # funksiya stansiya `active` bo'lmasa 404 berardi: pult
                # buzilgani uchun ta'mirga qo'yilgan stansiyadagi JONLI
                # seansni uzaytirib bo'lmasdi.
                "SELECT b.id, b.club_id, b.station_id, s.code AS station_code, b.status, b.hours,"
                "       b.rate_snapshot, b.play_amount, b.console_type, b.closed_at, b.customer_id,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       COALESCE(b.guest_name, u.display_name, u.first_name) AS guest_label,"
                "       u.telegram_id AS customer_telegram_id,"
                "       s.rate AS station_rate, r.kind AS room_kind,"
                "       c.name AS club_name, c.timezone AS club_tz, c.extend_max_hours"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " JOIN clubs c ON c.id = b.club_id"
                " LEFT JOIN rooms r ON r.id = s.room_id"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE b.id = :id AND b.club_id = :club_id"
            ),
            {"id": booking_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Bron topilmadi")
    return row


async def get_booking_detail(
    session: AsyncSession, *, club_id: int, booking_id: int
) -> dict[str, Any]:
    """Karta bosilganda: mijoz nima buyurtma qilgani, hisob qachon ochilgani,
    hozirgi holati — `pos/service.py::get_bill()`dan FARQI: status cheklovisiz
    (yopilgan/bekor qilingan bron uchun ham ishlaydi) va buyurtma satrlari bilan."""
    booking = await _load_booking_for_staff(session, club_id, booking_id)

    item_rows = (
        await session.execute(
            text(
                # `CANCELLED` chiqarib tashlanadi — bekor qilingan buyurtma
                # hisob tafsilotida ham ko'rinmasligi kerak (kassadagi
                # summa bilan mos bo'lsin, `pos/service.py::_orders_total()`).
                "SELECT oi.product_name, oi.qty, oi.price_snapshot"
                " FROM order_items oi JOIN orders o ON o.id = oi.order_id"
                " WHERE o.booking_id = :id AND o.club_id = :club_id"
                "   AND o.status <> 'CANCELLED'"
                " ORDER BY oi.id"
            ),
            {"id": booking_id, "club_id": club_id},
        )
    ).all()
    items = [
        {"product_name": r.product_name, "qty": r.qty, "price_snapshot": int(r.price_snapshot)}
        for r in item_rows
    ]
    orders_amount = sum(i["price_snapshot"] * i["qty"] for i in items)
    # Ustundan — `rate_snapshot * hours` EMAS: tarif vaqtga qarab
    # o'zgarganda bron ikki xil narxdagi bo'laklardan iborat bo'ladi
    # (`0037_rooms_tariffs.py`).
    play_amount = int(booking.play_amount)

    return {
        "id": booking.id,
        "station_id": booking.station_id,
        "station_code": booking.station_code,
        "status": booking.status,
        "starts_at": booking.starts_at.isoformat(),
        "ends_at": booking.ends_at.isoformat(),
        "hours": booking.hours,
        "rate_snapshot": int(booking.rate_snapshot),
        "guest_label": booking.guest_label,
        "closed": booking.closed_at is not None,
        "items": items,
        "play_amount": play_amount,
        "orders_amount": orders_amount,
        "total": play_amount + orders_amount,
    }


# Bitta amalda uzaytirish chegarasi — cheksiz uzaytirishni oldini oladi
# Bir marta uzaytirishning YUQORI chegarasi — DTO shu qiymatni ishlatadi.
# HAQIQIY chegara klubniki (`clubs.extend_max_hours`) va u servis qatlamida
# tekshiriladi: import paytida o'qiladigan konstanta tenant sozlamasi
# bo'la olmaydi.
EXTEND_HARD_MAX_HOURS = 12


async def extend_booking(
    session: AsyncSession, *, club_id: int, booking_id: int, staff_id: int, extra_hours: int
) -> dict[str, Any]:
    """Mijoz iltimosiga ko'ra vaqtni uzaytirish.

    Bandlik to'qnashuvi maxsus tekshirilmaydi — `bookings_no_overlap` EXCLUDE
    konstreyni `period` YANGILANGANDA ham ishlaydi (faqat INSERT'da emas),
    to'qnashsa `23P01` → global handler `409 SLOT_TAKEN`ga aylantiradi
    (`core/errors.py`).
    """
    booking = await _load_booking_for_staff(session, club_id, booking_id)

    club_max = int(booking.extend_max_hours)
    if not (1 <= extra_hours <= club_max):
        raise AppError(
            f"1 dan {club_max} soatgacha uzaytirish mumkin", code="EXTEND_RANGE_INVALID"
        )

    if booking.status != "CONFIRMED":
        raise AppError(
            "Faqat tasdiqlangan bron uzaytiriladi", code="BOOKING_NOT_CONFIRMED", status_code=409
        )
    if booking.closed_at is not None:
        raise AppError("Hisob allaqachon yopilgan", code="BILL_ALREADY_CLOSED", status_code=409)

    new_hours = booking.hours + extra_hours
    # `bookings_hours_range_ck` ni servis qatlamida ushlaymiz: 6 soatlik
    # bron uch marta uzaytirilsa 15 soat bo'lardi va CHECK buzilib xodim
    # 500 ko'rardi (`docs/audit-report.md` §2.4).
    if new_hours > MAX_TOTAL_HOURS:
        raise AppError(
            f"Bitta seans {MAX_TOTAL_HOURS} soatdan oshmaydi — hozir {booking.hours} soat",
            code="TOTAL_HOURS_EXCEEDED",
            status_code=409,
        )

    # FAQAT qo'shilgan oyna narxlanadi va mavjud summaga QO'SHILADI.
    #
    # Ilgari butun oyna (`starts_at`, `new_hours`) HOZIRGI tarif jadvali
    # bo'yicha qayta hisoblanardi. Bu snapshot invariantini buzardi: egasi
    # kechqurungi tarifni 21:00 da ko'tarsa, 18:00 da boshlangan seansni
    # uzaytirish mijozning ALLAQACHON o'ynagan uch soatini ham yangi narxga
    # ko'chirardi. Bron qilingandan keyin arxivlangan tarif esa uzaytirishni
    # umuman imkonsiz qilardi — narxlangan hujjat narxsiz bo'lib qolardi.
    #
    # `rate_snapshot` ham SHU SABABDAN tegilmaydi: u bron qilingan paytdagi
    # soatlik narx, keyingi o'zgarish uni qayta yozmaydi.
    club_view = SimpleNamespace(id=booking.club_id, timezone=booking.club_tz)
    station_view = SimpleNamespace(rate=booking.station_rate, room_kind=booking.room_kind)
    extra_amount, _ = await quote_play_amount(
        session,
        club=club_view,
        station=station_view,
        starts_at=booking.ends_at,
        hours=extra_hours,
        console_type=str(booking.console_type),
    )
    play_amount = int(booking.play_amount) + extra_amount

    row = (
        await session.execute(
            text(
                "UPDATE bookings SET hours = :hours, play_amount = :play,"
                " period = tstzrange(lower(period), upper(period) + make_interval(hours => :extra))"
                " WHERE id = :id"
                " RETURNING lower(period) AS starts_at, upper(period) AS ends_at"
            ),
            {
                "id": booking_id,
                "hours": new_hours,
                "extra": extra_hours,
                "play": play_amount,
            },
        )
    ).first()
    if row is None:  # amalda yuz bermaydi — yuqorida topilgani tasdiqlangan
        raise NotFound("Bron topilmadi")

    await log_action(
        action="booking_extended",
        target=booking.station_code,
        club_id=club_id,
        after={
            "extra_hours": extra_hours,
            "new_hours": new_hours,
            "play_amount": play_amount,
        },
    )

    return {
        "id": booking_id,
        "hours": new_hours,
        "starts_at": row.starts_at.isoformat(),
        "ends_at": row.ends_at.isoformat(),
    }


async def cancel_confirmed_booking(
    session: AsyncSession, *, club_id: int, booking_id: int, staff_id: int, reason: str | None
) -> None:
    """Mijoz kelmagan holatda xodim CONFIRMED bronni bekor qiladi.

    `reject_booking()`dan FARQI: u faqat mijoz yuborgan `PENDING` navbat
    uchun (hali tasdiqlanmagan); bu funksiya allaqachon tasdiqlangan, Live
    Board/Timeline'da "band" ko'rinayotgan bronni bekor qiladi.
    """
    booking = await _load_booking_for_staff(session, club_id, booking_id)
    if booking.status != "CONFIRMED":
        raise AppError(
            "Faqat tasdiqlangan bron bekor qilinadi", code="BOOKING_NOT_CONFIRMED", status_code=409
        )
    if booking.closed_at is not None:
        raise AppError(
            "Hisob allaqachon yopilgan — bekor qilib bo'lmaydi",
            code="BILL_ALREADY_CLOSED",
            status_code=409,
        )

    clean_reason = clean_name(reason, limit=300) if reason else None
    await session.execute(
        text(
            "UPDATE bookings SET status = 'CANCELLED', cancelled_by = :staff_id,"
            " cancelled_at = now(), cancel_reason = :reason WHERE id = :id"
        ),
        {"id": booking_id, "staff_id": staff_id, "reason": clean_reason},
    )

    await log_action(
        action="booking_cancelled",
        target=booking.station_code,
        club_id=club_id,
        after={"reason": clean_reason},
    )

    if booking.customer_id is not None:
        await notify.notify_customer_rejected(
            session,
            customer_id=booking.customer_id,
            club_name=booking.club_name,
            reason=clean_reason,
            # UPDATE'dan OLDIN o'qilgan — endi RLS uni ko'rsatmaydi
            telegram_id=booking.customer_telegram_id,
        )

async def customer_stats(session: AsyncSession, customer_id: int) -> dict[str, int]:
    """Mijoz profili statistikasi — REAL bronlardan hisoblanadi.

    Avval `miniapp/mock/data.ts::PROFILE_STATS` qotirilgan edi (18 seans /
    41 soat / 1 bekor / 0 kelmagan) va HAR BIR foydalanuvchida bir xil
    ko'rinardi (loyiha egasining so'rovi, 2026-08-16: "mijoz rolida seed
    va mock data qolib ketgan").

    "Kelmagan" (no-show) ATAYLAB YO'Q: bunday kuzatuv hali qurilmagan
    (`blacklist.tsx`, reja #32) — soxta nol ko'rsatishdan ko'ra maydonni
    umuman bermaslik. `sessions`/`hours` faqat YAKUNLANGAN (o'tib ketgan)
    tasdiqlangan bronlar bo'yicha: hali boshlanmagan bron "o'ynalgan
    soat" emas.
    """
    row = (
        await session.execute(
            text(
                "SELECT"
                "   count(*) FILTER ("
                "     WHERE status = 'CONFIRMED' AND upper(period) <= now()"
                "   ) AS sessions,"
                "   COALESCE(sum(hours) FILTER ("
                "     WHERE status = 'CONFIRMED' AND upper(period) <= now()"
                "   ), 0) AS hours,"
                "   count(*) FILTER (WHERE status = 'CANCELLED') AS cancelled,"
                "   count(*) FILTER ("
                "     WHERE status = 'CONFIRMED' AND upper(period) > now()"
                "   ) AS upcoming"
                " FROM bookings WHERE customer_id = :customer_id"
            ),
            {"customer_id": customer_id},
        )
    ).one()
    return {
        "sessions": int(row.sessions),
        "hours": int(row.hours),
        "cancelled": int(row.cancelled),
        "upcoming": int(row.upcoming),
    }


async def list_customer_bookings(session: AsyncSession, customer_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                # `c.timezone` — mijoz ilovasi vaqtni KLUB zonasida
                # ko'rsatishi uchun. Usiz telefon zonasida chiqardi va
                # mijoz o'z bronini boshqa soatda ko'rardi (audit
                # topilmasi, 2026-08-16; CLAUDE.md: "UI'da Asia/Tashkent").
                "SELECT b.id, b.status, b.hours, b.rate_snapshot, b.play_amount,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                # Hisob yopilgan bo'lsa bron TUGAGAN — oyna hali tugamagan
                # bo'lsa ham. Usiz mijoz ilovasida to'langan seans oyna
                # oxirigacha "aktiv" bo'lib turardi.
                "       b.closed_at IS NOT NULL AS closed,"
                "       s.code AS station_code, c.name AS club_name, c.timezone"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " JOIN clubs c ON c.id = b.club_id"
                " WHERE b.customer_id = :customer_id"
                " ORDER BY lower(b.period) DESC LIMIT 50"
            ),
            {"customer_id": customer_id},
        )
    ).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "hours": r.hours,
            "rate_snapshot": int(r.rate_snapshot),
            "play_amount": int(r.play_amount),
            "closed": bool(r.closed),
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "station_code": r.station_code,
            "club_name": r.club_name,
            "timezone": r.timezone,
        }
        for r in rows
    ]
