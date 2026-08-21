"""Bron marshrutlari — `/api/v1/clubs/{club_id}/...`.

Uch guruh:
  * ochiq o'qish (stansiyalar, bandlik) — `clubs_read`/`stations_read` bilan
    bir xil falsafa: klub `active` bo'lsa token shart emas
  * mijoz yozadi — `require_customer_token`, `POST .../bookings`
  * xodim boshqaradi — `require_staff`/`require_admin`, qolgan hammasi
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context, idempotency
from playbron.core.errors import BadRequest, Forbidden, NotFound
from playbron.deps import db, public_db, require_admin, require_customer_token, require_staff
from playbron.modules.bookings import service

STAFF_BOOKING_ROUTE = "POST /bookings/staff"
BOOKING_CONFIRM_ROUTE = "POST /bookings/{booking_id}/confirm"
BOOKING_REJECT_ROUTE = "POST /bookings/{booking_id}/reject"
BOOKING_EXTEND_ROUTE = "POST /bookings/{booking_id}/extend"
BOOKING_CANCEL_ROUTE = "POST /bookings/{booking_id}/cancel"

router = APIRouter(prefix="/clubs", tags=["bookings"])


def _assert_path_matches_header(club_id: int) -> None:
    """`staff/router.py`dagi bilan bir xil naqsh — yo'l va sarlavha klubi mos kelsin."""
    active = context.current().club_id
    if active is None or int(active) != int(club_id):
        raise Forbidden("Faol klub mos kelmadi", code="CLUB_MISMATCH")


# ── Sxemalar ──────────────────────────────────────────────────────────────


class ClubOut(BaseModel):
    id: int
    name: str
    address: str
    phone: str | None
    about: str
    cover_url: str | None
    opens_at_min: int
    closes_at_min: int
    timezone: str
    google_maps_url: str | None
    yandex_maps_url: str | None
    # Bron oynasi chegaralari — mijoz ilovasi davomiylik va kun tasmasini
    # SHULARDAN quradi. Ilgari ular klientda qotirilgan edi (`1..6`, `14`)
    # va klub sozlamasini o'zgartirsa ilova baribir eski variantni
    # ko'rsatib, so'rov serverda 422 bo'lardi.
    min_booking_hours: int
    max_booking_hours: int
    max_advance_days: int
    slot_step_min: int


class ClubDetailOut(ClubOut):
    status: str
    # Faqat xodim yo'lida — mijoz uzaytirmaydi.
    extend_max_hours: int


class StationOut(BaseModel):
    id: int
    code: str
    room_label: str
    # Eski (0023'dan oldingi) xonalarda hali bor — orqaga moslik uchun
    # ko'rsatiladi, lekin YANGI xonalarda `None` (reja #38): konsol turi
    # endi bron/hisob ochilganda tanlanadi, xonaga biriktirilmaydi.
    console_type: str | None
    rate: int
    status: str


class DayBookingOut(BaseModel):
    station_id: int
    starts_at: str
    ends_at: str
    status: str


# `0009_bookings.py::CONSOLE_TYPES` bilan bir xil ro'yxat. Ixtiyoriy —
# `service.py::_resolve_console_type()` xonaning eski (0023'dan oldingi)
# konsolidan foydalanadi berilmasa; konsolsiz (yangi) xonada esa MAJBURIY
# bo'lib qoladi (reja #38, loyiha egasi, 2026-08-16: "xonaga konsol
# biriktirmaslik kerak — mijoz/xodim bron/hisob ochishda tanlaydi").
_CONSOLE_TYPE_PATTERN = "^(ps3|ps4|ps4pro|ps5|ps5pro)$"


class CustomerBookingIn(BaseModel):
    station_id: int
    starts_at: datetime
    # Yuqori chegara — DB'ning MUTLAQ shifti (`bookings_hours_range_ck`),
    # klub sozlamasi emas. Haqiqiy oraliq `service._validate_window()` da
    # `clubs.min_booking_hours/max_booking_hours` bo'yicha tekshiriladi va
    # barqaror `HOURS_OUT_OF_RANGE` kodi bilan qaytadi. Bu yerda `6`
    # turgan edi: 8 soatga sozlangan klub Pydantic darajasida, kodsiz
    # 422 bilan rad etilardi va sozlama jimgina ishlamasdi.
    hours: int = Field(ge=1, le=service.MAX_TOTAL_HOURS)
    console_type: str | None = Field(default=None, pattern=_CONSOLE_TYPE_PATTERN)


class StaffBookingIn(BaseModel):
    station_id: int
    starts_at: datetime
    # Yuqori chegara — DB'ning MUTLAQ shifti (`bookings_hours_range_ck`),
    # klub sozlamasi emas. Haqiqiy oraliq `service._validate_window()` da
    # `clubs.min_booking_hours/max_booking_hours` bo'yicha tekshiriladi va
    # barqaror `HOURS_OUT_OF_RANGE` kodi bilan qaytadi. Bu yerda `6`
    # turgan edi: 8 soatga sozlangan klub Pydantic darajasida, kodsiz
    # 422 bilan rad etilardi va sozlama jimgina ishlamasdi.
    hours: int = Field(ge=1, le=service.MAX_TOTAL_HOURS)
    guest_name: str = Field(min_length=1, max_length=128)
    guest_phone: str = Field(min_length=1, max_length=32)
    console_type: str | None = Field(default=None, pattern=_CONSOLE_TYPE_PATTERN)


class QuoteOut(BaseModel):
    """Bron qilinmasdan hisoblangan narx."""

    play_amount: int
    rate_snapshot: int
    hours: int
    console_type: str


class BookingOut(BaseModel):
    id: int
    station_id: int
    status: str
    starts_at: str
    ends_at: str
    hours: int
    rate_snapshot: int
    # Oynaning TO'LIQ narxi. Tarif vaqtga qarab o'zgarsa
    # `rate_snapshot * hours` unga teng bo'lmaydi — hisob-kitob doim shu
    # ustundan ketadi (`0037_rooms_tariffs.py`).
    play_amount: int
    console_type: str
    prepaid_amount: int = 0
    guest_name: str | None = None
    guest_phone: str | None = None


class PendingBookingOut(BaseModel):
    id: int
    station_id: int
    station_code: str
    starts_at: str
    ends_at: str
    hours: int
    rate_snapshot: int
    # Oynaning TO'LIQ summasi. `rate_snapshot * hours` bilan hisoblamang:
    # tarif oyna ichida o'zgarsa ular teng bo'lmaydi.
    play_amount: int
    customer_name: str | None
    customer_phone: str | None


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ClubUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(default="", max_length=300)
    phone: str | None = Field(default=None, max_length=20)
    about: str = Field(default="", max_length=2000)
    opens_at_min: int = Field(ge=0, le=1559)
    closes_at_min: int = Field(ge=1, le=1560)
    # Chegaralar `0033` dagi CHECK konstreyntlari bilan bir xil.
    min_booking_hours: int = Field(default=1, ge=1, le=service.MAX_TOTAL_HOURS)
    max_booking_hours: int = Field(default=6, ge=1, le=service.MAX_TOTAL_HOURS)
    max_advance_days: int = Field(default=14, ge=1, le=365)
    extend_max_hours: int = Field(default=3, ge=1, le=service.EXTEND_HARD_MAX_HOURS)
    slot_step_min: int = Field(default=30, ge=15, le=60)
    # Xom havola — mijoz ilovasidagi "Manzil" tugmasi to'g'ridan-to'g'ri shuni
    # ochadi. Https tekshiruvi servis qatlamida (`service.py::update_club`).
    google_maps_url: str | None = Field(default=None, max_length=500)
    yandex_maps_url: str | None = Field(default=None, max_length=500)


class StationCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    room_label: str = Field(default="Standart", max_length=32)
    rate: int = Field(gt=0)


class StationUpdateIn(BaseModel):
    room_label: str = Field(default="Standart", max_length=32)
    rate: int = Field(gt=0)
    status: str = Field(pattern="^(active|maintenance)$")


# ── Ochiq o'qish ──────────────────────────────────────────────────────────


@router.get("", response_model=list[ClubOut])
async def list_clubs(session: Annotated[AsyncSession, Depends(public_db)]) -> list[ClubOut]:
    """Mijoz ilovasidagi klub katalogi — bitta umumiy bot, klub shu yerdan tanlanadi."""
    rows = await service.list_active_clubs(session)
    return [ClubOut(**r) for r in rows]


@router.get("/{club_id}/stations", response_model=list[StationOut])
async def list_stations(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(public_db)],
) -> list[StationOut]:
    rows = await service.list_stations(session, club_id)
    return [StationOut(**r) for r in rows]


@router.get(
    "/{club_id}",
    response_model=ClubDetailOut,
    dependencies=[Depends(require_staff)],
)
async def get_club(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ClubDetailOut:
    """Xodim/egasi o'z klubini `status`i bilan ko'radi — `draft` ham (`clubs_read`)."""
    _assert_path_matches_header(club_id)
    row = await service.get_club_for_staff(session, club_id)
    if row is None:
        raise NotFound("Klub topilmadi")
    return ClubDetailOut(**row)


@router.patch(
    "/{club_id}",
    response_model=ClubOut,
    dependencies=[Depends(require_admin)],
)
async def update_club(
    body: ClubUpdateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ClubOut:
    """Klub umumiy ma'lumoti — `clubs_write` (`0001`) org egasi/adminiga ochiq."""
    _assert_path_matches_header(club_id)
    row = await service.update_club(
        session,
        club_id=club_id,
        name=body.name,
        address=body.address,
        phone=body.phone,
        about=body.about,
        opens_at_min=body.opens_at_min,
        closes_at_min=body.closes_at_min,
        min_booking_hours=body.min_booking_hours,
        max_booking_hours=body.max_booking_hours,
        max_advance_days=body.max_advance_days,
        extend_max_hours=body.extend_max_hours,
        slot_step_min=body.slot_step_min,
        google_maps_url=body.google_maps_url,
        yandex_maps_url=body.yandex_maps_url,
    )
    return ClubOut(**row)


@router.post(
    "/{club_id}/publish",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
async def publish_club(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> None:
    """Klub egasi/admini `draft` klubni o'zi faollashtiradi — super admin shart emas."""
    _assert_path_matches_header(club_id)
    await service.publish_club(session, club_id=club_id)


@router.get(
    "/{club_id}/stations/manage",
    response_model=list[StationOut],
    dependencies=[Depends(require_admin)],
)
async def list_stations_for_management(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> list[StationOut]:
    """Boshqaruv ro'yxati — `maintenance` xonalar ham (ochiq `/stations` faqat `active`)."""
    _assert_path_matches_header(club_id)
    rows = await service.list_all_stations(session, club_id)
    return [StationOut(**r) for r in rows]


@router.post(
    "/{club_id}/stations",
    response_model=StationOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_station(
    body: StationCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> StationOut:
    _assert_path_matches_header(club_id)
    row = await service.create_station(
        session,
        club_id=club_id,
        code=body.code,
        room_label=body.room_label,
        rate=body.rate,
    )
    return StationOut(**row)


@router.patch(
    "/{club_id}/stations/{station_id}",
    response_model=StationOut,
    dependencies=[Depends(require_admin)],
)
async def update_station(
    body: StationUpdateIn,
    club_id: Annotated[int, Path()],
    station_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> StationOut:
    _assert_path_matches_header(club_id)
    row = await service.update_station(
        session,
        club_id=club_id,
        station_id=station_id,
        room_label=body.room_label,
        rate=body.rate,
        status=body.status,
    )
    return StationOut(**row)


# ── Xonalar va tariflar ───────────────────────────────────────────────────
# Jadvallar `0037_rooms_tariffs.py` da tayyor va `pricing.py` ularni
# o'qiydi, lekin boshqaruv yo'li yo'q edi — tarif faqat xom SQL bilan
# kiritilardi (`CLAUDE.md`, «Ma'lum texnik qarz»).
#
# Hammasi `require_admin`: `rooms_write`/`tariffs_write` policy'lari ham
# faqat OWNER/ADMIN ga ochiq, guard esa uning USTIGA qo'shimcha qatlam.
# Ro'yxatlar ham admin ostida — `0033` dagi ochiq `*_read` policy'si
# MIJOZ yo'li uchun (narxni bron qilishdan oldin ko'rish), bu yerdagisi
# esa boshqaruv ro'yxati: nofaol qatorlarni ham qaytaradi.
#
# O'chirish YO'Q — `is_active` bilan arxivlanadi (`products` naqshi):
# yopilgan bronlarning narxi shu qatorlar orqali hisoblangan.


class RoomOut(BaseModel):
    id: int
    name: str
    # Erkin matn: klub o'zi nomlaydi. Tarif shu qiymatga qarab
    # yo'naltiriladi (`tariffs.room_kind`).
    kind: str
    sort: int
    is_active: bool


class RoomCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: str = Field(default="Standart", max_length=32)
    sort: int = Field(default=0, ge=0, le=9999)


class RoomUpdateIn(RoomCreateIn):
    is_active: bool = True


class TariffOut(BaseModel):
    id: int
    name: str
    days_mask: int
    from_min: int
    to_min: int
    price_per_hour: int
    priority: int
    console_type: str | None
    room_kind: str | None
    is_active: bool


class TariffCreateIn(BaseModel):
    """Chegaralar `tariffs_*_ck` (`0033`) bilan bir xil.

    `to_min` 1440 dan katta bo'lishi MUMKIN — yarim tundan o'tuvchi oyna
    (22:00–02:00 → 1320..1560) shunday ifodalanadi.
    """

    name: str = Field(min_length=1, max_length=64)
    # Dushanba = 1-bit ... yakshanba = 64-bit. `0` — hech qanday kun,
    # ya'ni tarif hech qachon qo'llanmasdi.
    days_mask: int = Field(ge=1, le=127)
    from_min: int = Field(ge=0, le=1439)
    to_min: int = Field(ge=1, le=2880)
    price_per_hour: int = Field(gt=0)
    priority: int = Field(default=0, ge=0, le=1000)
    # `None` — har qanday konsolga / xonaga.
    console_type: str | None = Field(default=None, pattern=_CONSOLE_TYPE_PATTERN)
    room_kind: str | None = Field(default=None, max_length=32)


class TariffUpdateIn(TariffCreateIn):
    is_active: bool = True


@router.get(
    "/{club_id}/rooms",
    response_model=list[RoomOut],
    dependencies=[Depends(require_admin)],
)
async def list_rooms(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> list[RoomOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_rooms(session, club_id)
    return [RoomOut(**r) for r in rows]


@router.post(
    "/{club_id}/rooms",
    response_model=RoomOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_room(
    body: RoomCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> RoomOut:
    _assert_path_matches_header(club_id)
    row = await service.create_room(
        session,
        club_id=club_id,
        name=body.name,
        kind=body.kind,
        sort=body.sort,
    )
    return RoomOut(**row)


@router.patch(
    "/{club_id}/rooms/{room_id}",
    response_model=RoomOut,
    dependencies=[Depends(require_admin)],
)
async def update_room(
    body: RoomUpdateIn,
    club_id: Annotated[int, Path()],
    room_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> RoomOut:
    _assert_path_matches_header(club_id)
    row = await service.update_room(
        session,
        club_id=club_id,
        room_id=room_id,
        name=body.name,
        kind=body.kind,
        sort=body.sort,
        is_active=body.is_active,
    )
    return RoomOut(**row)


@router.get(
    "/{club_id}/tariffs",
    response_model=list[TariffOut],
    dependencies=[Depends(require_admin)],
)
async def list_tariffs(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> list[TariffOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_tariffs(session, club_id)
    return [TariffOut(**r) for r in rows]


@router.post(
    "/{club_id}/tariffs",
    response_model=TariffOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_tariff(
    body: TariffCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> TariffOut:
    _assert_path_matches_header(club_id)
    row = await service.create_tariff(
        session,
        club_id=club_id,
        name=body.name,
        days_mask=body.days_mask,
        from_min=body.from_min,
        to_min=body.to_min,
        price_per_hour=body.price_per_hour,
        priority=body.priority,
        console_type=body.console_type,
        room_kind=body.room_kind,
    )
    return TariffOut(**row)


@router.patch(
    "/{club_id}/tariffs/{tariff_id}",
    response_model=TariffOut,
    dependencies=[Depends(require_admin)],
)
async def update_tariff(
    body: TariffUpdateIn,
    club_id: Annotated[int, Path()],
    tariff_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> TariffOut:
    _assert_path_matches_header(club_id)
    row = await service.update_tariff(
        session,
        club_id=club_id,
        tariff_id=tariff_id,
        name=body.name,
        days_mask=body.days_mask,
        from_min=body.from_min,
        to_min=body.to_min,
        price_per_hour=body.price_per_hour,
        priority=body.priority,
        console_type=body.console_type,
        room_kind=body.room_kind,
        is_active=body.is_active,
    )
    return TariffOut(**row)


@router.get("/{club_id}/bookings/day", response_model=list[DayBookingOut])
async def list_day_bookings(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(public_db)],
    date: Annotated[str, Query(description="YYYY-MM-DD, klub vaqt zonasida")],
) -> list[DayBookingOut]:
    try:
        day = datetime.fromisoformat(date)
    except ValueError as exc:
        raise BadRequest("Sana YYYY-MM-DD ko'rinishida bo'lsin", code="DATE_INVALID") from exc

    rows = await service.list_day_bookings(session, club_id, day)
    return [DayBookingOut(**r) for r in rows]


class TimelineBookingOut(BaseModel):
    id: int
    station_id: int
    station_code: str
    room_label: str
    console_type: str
    starts_at: str
    ends_at: str
    status: str
    closed: bool
    guest_label: str | None


@router.get(
    "/{club_id}/bookings/timeline",
    response_model=list[TimelineBookingOut],
    dependencies=[Depends(require_staff)],
)
async def timeline(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    date: Annotated[str, Query(description="YYYY-MM-DD, klub vaqt zonasida")],
) -> list[TimelineBookingOut]:
    """`timeline.tsx` — xodim uchun kunlik jadval, mehmon ismi va stansiya
    ma'lumoti bilan (`list_day_bookings` mijoz bo'sh-slot hisobiga
    mo'ljallangan, bu yerga mos emas — xom oraliq qaytaradi, mehmon ismi
    yo'q)."""
    _assert_path_matches_header(club_id)
    try:
        day = datetime.fromisoformat(date)
    except ValueError as exc:
        raise BadRequest("Sana YYYY-MM-DD ko'rinishida bo'lsin", code="DATE_INVALID") from exc

    rows = await service.list_timeline(session, club_id, day)
    return [TimelineBookingOut(**r) for r in rows]


# ── Mijoz ─────────────────────────────────────────────────────────────────


@router.post(
    "/{club_id}/bookings",
    response_model=BookingOut,
    status_code=201,
    dependencies=[Depends(require_customer_token)],
)
async def create_booking(
    body: CustomerBookingIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> BookingOut:
    """Mijoz o'zi bron qiladi — to'lovsiz, `PENDING` holatda.

    Xodimga bildirishnoma bu funksiya ichida (best-effort) ketadi.
    """
    result = await service.create_customer_booking(
        session,
        club_id=club_id,
        customer_id=context.current().user_id,
        station_id=body.station_id,
        starts_at=body.starts_at,
        hours=body.hours,
        console_type=body.console_type,
    )
    return BookingOut(**result)


@router.post(
    "/{club_id}/bookings/quote",
    response_model=QuoteOut,
    dependencies=[Depends(require_customer_token)],
)
async def quote_booking(
    body: CustomerBookingIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> QuoteOut:
    """Narxni bron QILMASDAN hisoblaydi.

    `0037_rooms_tariffs.py` dan keyin narx vaqtga qarab o'zgaradi —
    mijoz ilovasi uni o'zi hisoblab bera olmaydi va `CLAUDE.md`
    («Frontend») bo'yicha hisoblamasligi ham kerak. Usiz mijoz jami
    summani faqat bron qilib bo'lgandan keyin bilardi.
    """
    result = await service.quote_booking(
        session,
        club_id=club_id,
        station_id=body.station_id,
        starts_at=body.starts_at,
        hours=body.hours,
        console_type=body.console_type,
    )
    return QuoteOut(**result)


# ── Xodim ─────────────────────────────────────────────────────────────────


@router.post(
    "/{club_id}/bookings/staff",
    response_model=BookingOut,
    status_code=201,
    dependencies=[Depends(require_staff)],
)
async def create_staff_booking(
    body: StaffBookingIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BookingOut:
    """Xodim qo'lda bron ochadi — telefon/kelib bron qiladigan mijoz uchun.

    Darhol `CONFIRMED`: xodimning o'zi tasdiqlovchi.

    `Idempotency-Key` — tarmoq sekin bo'lib qayta yuborilsa yoki tugma ikki
    marta bosilsa, ikkinchi bron OCHILMASIN (`core/idempotency.py`).
    """
    _assert_path_matches_header(club_id)
    user_id = context.current().user_id or 0
    outcome = await idempotency.begin(
        session,
        key=idempotency_key,
        route=STAFF_BOOKING_ROUTE,
        club_id=club_id,
        user_id=user_id,
        path_params={},
        body=body.model_dump(mode="json"),
    )
    if outcome.replay is not None:
        response.status_code = outcome.replay["status"]
        return BookingOut(**outcome.replay["body"])

    result = await service.create_staff_booking(
        session,
        club_id=club_id,
        created_by=user_id,
        station_id=body.station_id,
        starts_at=body.starts_at,
        hours=body.hours,
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
        console_type=body.console_type,
    )
    await idempotency.finish(session, row_id=outcome.row_id, status_code=201, response_body=result)
    return BookingOut(**result)


@router.get(
    "/{club_id}/bookings/pending",
    response_model=list[PendingBookingOut],
    dependencies=[Depends(require_staff)],
)
async def list_pending(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> list[PendingBookingOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_pending_bookings(session, club_id)
    return [PendingBookingOut(**r) for r in rows]


@router.post(
    "/{club_id}/bookings/{booking_id}/confirm",
    status_code=204,
    dependencies=[Depends(require_staff)],
)
async def confirm(
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> None:
    _assert_path_matches_header(club_id)
    user_id = context.current().user_id or 0
    outcome = await idempotency.begin(
        session,
        key=idempotency_key,
        route=BOOKING_CONFIRM_ROUTE,
        club_id=club_id,
        user_id=user_id,
        path_params={"booking_id": booking_id},
        body={},
    )
    if outcome.replay is not None:
        return

    await service.confirm_booking(
        session, club_id=club_id, booking_id=booking_id, staff_id=context.current().user_id
    )
    await idempotency.finish(session, row_id=outcome.row_id, status_code=204, response_body={})


@router.post(
    "/{club_id}/bookings/{booking_id}/reject",
    status_code=204,
    dependencies=[Depends(require_staff)],
)
async def reject(
    body: RejectIn,
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> None:
    _assert_path_matches_header(club_id)
    user_id = context.current().user_id or 0
    outcome = await idempotency.begin(
        session,
        key=idempotency_key,
        route=BOOKING_REJECT_ROUTE,
        club_id=club_id,
        user_id=user_id,
        path_params={"booking_id": booking_id},
        body=body.model_dump(mode="json"),
    )
    if outcome.replay is not None:
        return

    await service.reject_booking(
        session,
        club_id=club_id,
        booking_id=booking_id,
        staff_id=context.current().user_id,
        reason=body.reason,
    )
    await idempotency.finish(session, row_id=outcome.row_id, status_code=204, response_body={})


class OrderItemOut(BaseModel):
    product_name: str
    qty: int
    price_snapshot: int


class BookingDetailOut(BaseModel):
    id: int
    station_id: int
    station_code: str
    status: str
    starts_at: str
    ends_at: str
    hours: int
    rate_snapshot: int
    guest_label: str | None
    closed: bool
    items: list[OrderItemOut]
    play_amount: int
    orders_amount: int
    total: int
    # Optimistik konkurrensiya — `extend`ga shu qiymat `expected_version`
    # sifatida yuboriladi (`0041_booking_version_command_id.py`, audit §15).
    version: int


@router.get(
    "/{club_id}/bookings/{booking_id}/detail",
    response_model=BookingDetailOut,
    dependencies=[Depends(require_staff)],
)
async def booking_detail(
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> BookingDetailOut:
    """Live Board/Timeline — karta tanlanganda hisob detali (reja #36)."""
    _assert_path_matches_header(club_id)
    row = await service.get_booking_detail(session, club_id=club_id, booking_id=booking_id)
    return BookingDetailOut(**row)


class ExtendIn(BaseModel):
    # DTO faqat DB darajasidagi QATTIQ chegarani biladi. Klubning o'z
    # chegarasi (`clubs.extend_max_hours`) servisda tekshiriladi — import
    # paytida o'qiladigan konstanta tenantga qarab o'zgara olmaydi.
    extra_hours: int = Field(ge=1, le=service.EXTEND_HARD_MAX_HOURS)
    # Ixtiyoriy — `BookingDetailOut.version`dan olinadi. Berilmasa eski
    # (tekshiruvsiz) xatti-harakat, berilib mos kelmasa `409 VERSION_CONFLICT`
    # (`0041_booking_version_command_id.py`, audit §15).
    expected_version: int | None = Field(default=None, ge=1)


class ExtendOut(BaseModel):
    id: int
    hours: int
    starts_at: str
    ends_at: str
    version: int


@router.post(
    "/{club_id}/bookings/{booking_id}/extend",
    response_model=ExtendOut,
    dependencies=[Depends(require_staff)],
)
async def extend(
    body: ExtendIn,
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ExtendOut:
    """Mijoz iltimosiga ko'ra vaqtni uzaytirish (reja #36)."""
    _assert_path_matches_header(club_id)
    user_id = context.current().user_id or 0
    outcome = await idempotency.begin(
        session,
        key=idempotency_key,
        route=BOOKING_EXTEND_ROUTE,
        club_id=club_id,
        user_id=user_id,
        path_params={"booking_id": booking_id},
        body=body.model_dump(mode="json"),
    )
    if outcome.replay is not None:
        response.status_code = outcome.replay["status"]
        return ExtendOut(**outcome.replay["body"])

    row = await service.extend_booking(
        session,
        club_id=club_id,
        booking_id=booking_id,
        staff_id=context.current().user_id,
        extra_hours=body.extra_hours,
        expected_version=body.expected_version,
        command_id=idempotency_key,
    )
    await idempotency.finish(session, row_id=outcome.row_id, status_code=200, response_body=row)
    return ExtendOut(**row)


@router.post(
    "/{club_id}/bookings/{booking_id}/cancel",
    status_code=204,
    dependencies=[Depends(require_staff)],
)
async def cancel(
    body: RejectIn,
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> None:
    """Mijoz kelmagan — tasdiqlangan bronni Live Board/Timeline'dan bekor
    qilish (reja #36). `reject`dan farqli, PENDING emas, CONFIRMED uchun."""
    _assert_path_matches_header(club_id)
    user_id = context.current().user_id or 0
    outcome = await idempotency.begin(
        session,
        key=idempotency_key,
        route=BOOKING_CANCEL_ROUTE,
        club_id=club_id,
        user_id=user_id,
        path_params={"booking_id": booking_id},
        body=body.model_dump(mode="json"),
    )
    if outcome.replay is not None:
        return

    await service.cancel_confirmed_booking(
        session,
        club_id=club_id,
        booking_id=booking_id,
        staff_id=context.current().user_id,
        reason=body.reason,
        command_id=idempotency_key,
    )
    await idempotency.finish(session, row_id=outcome.row_id, status_code=204, response_body={})
