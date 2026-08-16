"""Bron biznes mantig'i — validatsiya + yozish. RLS defense-in-depth,
bu yerdagi tekshiruvlar HAKAM (`docs/05-auth-redesign.md` uslubi bilan bir xil).
"""

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.audit import log_action
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

    try:
        station_id = await session.scalar(
            text(
                "INSERT INTO stations (club_id, code, room_label, rate, status)"
                " VALUES (:club_id, :code, :room_label, :rate, 'active')"
                " RETURNING id"
            ),
            {
                "club_id": club_id,
                "code": code,
                "room_label": room_label.strip() or "Standart",
                "rate": rate,
            },
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "23505":
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

    row = (
        await session.execute(
            text(
                "UPDATE stations SET room_label = :room_label, rate = :rate, status = :status"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id, code, room_label, console_type, rate, status"
            ),
            {
                "room_label": room_label.strip() or "Standart",
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
                "SELECT id, code, console_type, rate, status FROM stations"
                " WHERE id = :id AND club_id = :club_id"
            ),
            {"id": station_id, "club_id": club_id},
        )
    ).first()
    if station is None or station.status != "active":
        raise NotFound("Xona topilmadi")

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
    console_type: str | None = None,
) -> dict[str, Any]:
    club, station = await _load_club_and_station(session, club_id, station_id)
    _validate_window(starts_at, hours)
    resolved_console = _resolve_console_type(console_type, station)

    ends_at = starts_at + timedelta(hours=hours)
    rate = int(station.rate)

    booking_id = await session.scalar(
        text(
            "INSERT INTO bookings"
            " (club_id, station_id, customer_id, source, status, period, hours,"
            "  rate_snapshot, console_type)"
            " VALUES (:club_id, :station_id, :customer_id, 'MINIAPP', 'PENDING',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate, :console_type)"
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
    _validate_window(starts_at, hours)
    resolved_console = _resolve_console_type(console_type, station)

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
            "  period, hours, rate_snapshot, console_type, created_by, confirmed_by,"
            "  confirmed_at)"
            " VALUES (:club_id, :station_id, :guest_name, :guest_phone, 'STAFF', 'CONFIRMED',"
            "         tstzrange(:starts_at, :ends_at), :hours, :rate, :console_type,"
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
                "       c.name AS club_name, c.timezone AS club_tz,"
                "       u.telegram_id AS customer_telegram_id"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
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
                "SELECT b.id, b.station_id, s.code AS station_code, b.status, b.hours,"
                "       b.rate_snapshot, b.closed_at, b.customer_id,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       COALESCE(b.guest_name, u.display_name, u.first_name) AS guest_label,"
                "       u.telegram_id AS customer_telegram_id,"
                "       c.name AS club_name, c.timezone AS club_tz"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
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
    play_amount = int(booking.rate_snapshot) * booking.hours

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
EXTEND_MAX_HOURS = 3


async def extend_booking(
    session: AsyncSession, *, club_id: int, booking_id: int, staff_id: int, extra_hours: int
) -> dict[str, Any]:
    """Mijoz iltimosiga ko'ra vaqtni uzaytirish.

    Bandlik to'qnashuvi maxsus tekshirilmaydi — `bookings_no_overlap` EXCLUDE
    konstreyni `period` YANGILANGANDA ham ishlaydi (faqat INSERT'da emas),
    to'qnashsa `23P01` → global handler `409 SLOT_TAKEN`ga aylantiradi
    (`core/errors.py`).
    """
    if not (1 <= extra_hours <= EXTEND_MAX_HOURS):
        raise AppError(
            f"1 dan {EXTEND_MAX_HOURS} soatgacha uzaytirish mumkin", code="EXTEND_RANGE_INVALID"
        )

    booking = await _load_booking_for_staff(session, club_id, booking_id)
    if booking.status != "CONFIRMED":
        raise AppError(
            "Faqat tasdiqlangan bron uzaytiriladi", code="BOOKING_NOT_CONFIRMED", status_code=409
        )
    if booking.closed_at is not None:
        raise AppError("Hisob allaqachon yopilgan", code="BILL_ALREADY_CLOSED", status_code=409)

    new_hours = booking.hours + extra_hours
    row = (
        await session.execute(
            text(
                "UPDATE bookings SET hours = :hours,"
                " period = tstzrange(lower(period), upper(period) + make_interval(hours => :extra))"
                " WHERE id = :id"
                " RETURNING lower(period) AS starts_at, upper(period) AS ends_at"
            ),
            {"id": booking_id, "hours": new_hours, "extra": extra_hours},
        )
    ).first()
    if row is None:  # amalda yuz bermaydi — yuqorida topilgani tasdiqlangan
        raise NotFound("Bron topilmadi")

    await log_action(
        action="booking_extended",
        target=booking.station_code,
        club_id=club_id,
        after={"extra_hours": extra_hours, "new_hours": new_hours},
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
