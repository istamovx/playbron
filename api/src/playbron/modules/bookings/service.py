"""Bron biznes mantig'i — validatsiya + yozish. RLS defense-in-depth,
bu yerdagi tekshiruvlar HAKAM (`docs/05-auth-redesign.md` uslubi bilan bir xil).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.errors import AppError, Forbidden, NotFound
from playbron.core.text import clean_name
from playbron.modules.bookings import notify
from playbron.modules.bot.contact import normalize_phone

MIN_HOURS = 1
MAX_HOURS = 6
# Bugundan boshlab necha kun oldinga bron qilish mumkin (BUILD-BRIEF §…,
# yangi narx modeli bilan ziddiyatsiz — faqat oldindan bron oynasi)
MAX_ADVANCE_DAYS = 14
# Bron boshlanishidan necha daqiqa oldin hali ham qabul qilinadi (soat
# ustida turgan foydalanuvchi "hozir" ni bir necha soniya kech bosishi mumkin)
PAST_GRACE_MIN = 2


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
    console_type: str,
    rate: int,
) -> dict[str, Any]:
    if console_type not in CONSOLE_TYPES:
        raise AppError("Noma'lum konsol turi", code="CONSOLE_TYPE_INVALID")
    if rate <= 0:
        raise AppError("Narx musbat bo'lsin", code="RATE_INVALID")

    code = code.strip()
    if not code:
        raise AppError("Xona kodini kiriting", code="CODE_REQUIRED")

    try:
        station_id = await session.scalar(
            text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate, status)"
                " VALUES (:club_id, :code, :room_label, :console_type, :rate, 'active')"
                " RETURNING id"
            ),
            {
                "club_id": club_id,
                "code": code,
                "room_label": room_label.strip() or "Standart",
                "console_type": console_type,
                "rate": rate,
            },
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "23505":
            raise AppError("Bu kod bilan xona allaqachon bor", code="STATION_CODE_TAKEN") from exc
        raise

    return {
        "id": station_id,
        "code": code,
        "room_label": room_label.strip() or "Standart",
        "console_type": console_type,
        "rate": rate,
        "status": "active",
    }


async def update_station(
    session: AsyncSession,
    *,
    club_id: int,
    station_id: int,
    room_label: str,
    console_type: str,
    rate: int,
    status: str,
) -> dict[str, Any]:
    if console_type not in CONSOLE_TYPES:
        raise AppError("Noma'lum konsol turi", code="CONSOLE_TYPE_INVALID")
    if rate <= 0:
        raise AppError("Narx musbat bo'lsin", code="RATE_INVALID")
    if status not in ("active", "maintenance"):
        raise AppError("Noma'lum holat", code="STATUS_INVALID")

    row = (
        await session.execute(
            text(
                "UPDATE stations SET room_label = :room_label, console_type = :console_type,"
                " rate = :rate, status = :status"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id, code, room_label, console_type, rate, status"
            ),
            {
                "room_label": room_label.strip() or "Standart",
                "console_type": console_type,
                "rate": rate,
                "status": status,
                "id": station_id,
                "club_id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Xona topilmadi")
    return _station_row_to_dict(row)


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
    google_maps_url = _clean_maps_url(google_maps_url, field_label="Google Maps")
    yandex_maps_url = _clean_maps_url(yandex_maps_url, field_label="Yandex Maps")

    row = (
        await session.execute(
            text(
                "UPDATE clubs SET name = :name, address = :address, phone = :phone,"
                " about = :about, opens_at_min = :opens_at_min, closes_at_min = :closes_at_min,"
                " google_maps_url = :google_maps_url, yandex_maps_url = :yandex_maps_url"
                " WHERE id = :id"
                " RETURNING id, name, address, phone, about, cover_url,"
                "           opens_at_min, closes_at_min, timezone,"
                "           google_maps_url, yandex_maps_url"
            ),
            {
                "name": name.strip(),
                "address": address.strip(),
                "phone": phone.strip() if phone else None,
                "about": about.strip(),
                "opens_at_min": opens_at_min,
                "closes_at_min": closes_at_min,
                "google_maps_url": google_maps_url,
                "yandex_maps_url": yandex_maps_url,
                "id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Klub topilmadi")

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
        "google_maps_url": row.google_maps_url,
        "yandex_maps_url": row.yandex_maps_url,
    }


async def list_day_bookings(
    session: AsyncSession, club_id: int, day: datetime
) -> list[dict[str, Any]]:
    """Berilgan kunning FAOL (PENDING/CONFIRMED) bronlari — bo'sh slot hisoblash uchun.

    Frontend `freeStations` mantig'ini o'zgartirmasin deb, xom band oraliqlar
    qaytariladi — bo'sh slotni hisoblash mijoz tomonida qoladi.
    """
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

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


async def _load_club_and_station(
    session: AsyncSession, club_id: int, station_id: int
) -> tuple[Any, Any]:
    club = (
        await session.execute(
            text("SELECT id, name, timezone, status FROM clubs WHERE id = :id"), {"id": club_id}
        )
    ).first()
    if club is None or club.status != "active":
        raise NotFound("Klub topilmadi")

    station = (
        await session.execute(
            text(
                "SELECT id, code, rate, status FROM stations WHERE id = :id AND club_id = :club_id"
            ),
            {"id": station_id, "club_id": club_id},
        )
    ).first()
    if station is None or station.status != "active":
        raise NotFound("Xona topilmadi")

    return club, station


def _validate_window(starts_at: datetime, hours: int) -> datetime:
    if not (MIN_HOURS <= hours <= MAX_HOURS):
        raise AppError(
            f"Davomiylik {MIN_HOURS}–{MAX_HOURS} soat oralig'ida bo'lsin",
            code="HOURS_OUT_OF_RANGE",
        )

    if starts_at.tzinfo is None:
        raise AppError("Vaqt zona bilan berilishi kerak", code="STARTS_AT_INVALID")

    now = datetime.now(UTC)
    if starts_at < now - timedelta(minutes=PAST_GRACE_MIN):
        raise AppError("O'tib ketgan vaqtga bron qilib bo'lmaydi", code="STARTS_AT_PAST")

    if starts_at > now + timedelta(days=MAX_ADVANCE_DAYS):
        raise AppError(
            f"Bron faqat {MAX_ADVANCE_DAYS} kun oldinga qilinadi", code="STARTS_AT_TOO_FAR"
        )

    return starts_at


async def create_customer_booking(
    session: AsyncSession,
    *,
    club_id: int,
    customer_id: int,
    station_id: int,
    starts_at: datetime,
    hours: int,
) -> dict[str, Any]:
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours)

    ends_at = starts_at + timedelta(hours=hours)
    rate = int(station.rate)

    booking_id = await session.scalar(
        text(
            "INSERT INTO bookings"
            " (club_id, station_id, customer_id, source, status, period, hours, rate_snapshot)"
            " VALUES (:club_id, :station_id, :customer_id, 'MINIAPP', 'PENDING',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate)"
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
) -> dict[str, Any]:
    """Xodim qo'lda ochadi — telefon/kelib bron qilgan mijoz uchun.

    `status='CONFIRMED'` DARHOL: xodimning o'zi tasdiqlovchi, ikkinchi
    bosqich shart emas — "qog'ozbozlikdan qutilish" aynan shu.
    """
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours)

    name = clean_name(guest_name, limit=128)
    if len(name) < 2:
        raise AppError("Mijoz ismi kamida 2 belgi bo'lsin", code="GUEST_NAME_INVALID")

    phone = normalize_phone(guest_phone)
    if phone is None:
        raise AppError("Telefon raqami +998XXXXXXXXX ko'rinishida bo'lsin", code="PHONE_INVALID")

    ends_at = starts_at + timedelta(hours=hours)
    rate = int(station.rate)

    booking_id = await session.scalar(
        text(
            "INSERT INTO bookings"
            " (club_id, station_id, guest_name, guest_phone, source, status,"
            "  period, hours, rate_snapshot, created_by, confirmed_by, confirmed_at)"
            " VALUES (:club_id, :station_id, :guest_name, :guest_phone, 'STAFF', 'CONFIRMED',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate, :created_by,"
            "         :created_by, now())"
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
        "guest_name": name,
        "guest_phone": phone,
    }


async def list_pending_bookings(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT b.id, b.station_id, s.code AS station_code,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       b.hours, b.rate_snapshot,"
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
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
        }
        for r in rows
    ]


async def _load_pending_booking(session: AsyncSession, club_id: int, booking_id: int) -> Any:
    row = (
        await session.execute(
            text(
                "SELECT b.id, b.customer_id, b.status, b.source, b.hours,"
                "       lower(b.period) AS starts_at, s.code AS station_code,"
                "       c.name AS club_name, c.timezone AS club_tz"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " JOIN clubs c ON c.id = b.club_id"
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
            station_code=booking.station_code,
            starts_label=notify.format_starts_at(booking.starts_at, booking.club_tz),
            hours=booking.hours,
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
        )


async def list_customer_bookings(session: AsyncSession, customer_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT b.id, b.status, b.hours, b.rate_snapshot,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       s.code AS station_code, c.name AS club_name"
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
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "station_code": r.station_code,
            "club_name": r.club_name,
        }
        for r in rows
    ]
