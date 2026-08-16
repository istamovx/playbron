"""Bron marshrutlari — `/api/v1/clubs/{club_id}/...`.

Uch guruh:
  * ochiq o'qish (stansiyalar, bandlik) — `clubs_read`/`stations_read` bilan
    bir xil falsafa: klub `active` bo'lsa token shart emas
  * mijoz yozadi — `require_customer_token`, `POST .../bookings`
  * xodim boshqaradi — `require_staff`/`require_admin`, qolgan hammasi
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import BadRequest, Forbidden, NotFound
from playbron.deps import db, public_db, require_admin, require_customer_token, require_staff
from playbron.modules.bookings import service

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


class ClubDetailOut(ClubOut):
    status: str


class StationOut(BaseModel):
    id: int
    code: str
    room_label: str
    console_type: str
    rate: int
    status: str


class DayBookingOut(BaseModel):
    station_id: int
    starts_at: str
    ends_at: str
    status: str


class CustomerBookingIn(BaseModel):
    station_id: int
    starts_at: datetime
    hours: int = Field(ge=1, le=6)


class StaffBookingIn(BaseModel):
    station_id: int
    starts_at: datetime
    hours: int = Field(ge=1, le=6)
    guest_name: str = Field(min_length=1, max_length=128)
    guest_phone: str = Field(min_length=1, max_length=32)


class BookingOut(BaseModel):
    id: int
    station_id: int
    status: str
    starts_at: str
    ends_at: str
    hours: int
    rate_snapshot: int
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
    # Xom havola — mijoz ilovasidagi "Manzil" tugmasi to'g'ridan-to'g'ri shuni
    # ochadi. Https tekshiruvi servis qatlamida (`service.py::update_club`).
    google_maps_url: str | None = Field(default=None, max_length=500)
    yandex_maps_url: str | None = Field(default=None, max_length=500)


class StationCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    room_label: str = Field(default="Standart", max_length=32)
    console_type: str = Field(pattern="^(ps3|ps4|ps4pro|ps5|ps5pro)$")
    rate: int = Field(gt=0)


class StationUpdateIn(BaseModel):
    room_label: str = Field(default="Standart", max_length=32)
    console_type: str = Field(pattern="^(ps3|ps4|ps4pro|ps5|ps5pro)$")
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
        console_type=body.console_type,
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
        console_type=body.console_type,
        rate=body.rate,
        status=body.status,
    )
    return StationOut(**row)


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
    )
    return BookingOut(**result)


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
) -> BookingOut:
    """Xodim qo'lda bron ochadi — telefon/kelib bron qiladigan mijoz uchun.

    Darhol `CONFIRMED`: xodimning o'zi tasdiqlovchi.
    """
    _assert_path_matches_header(club_id)
    result = await service.create_staff_booking(
        session,
        club_id=club_id,
        created_by=context.current().user_id,
        station_id=body.station_id,
        starts_at=body.starts_at,
        hours=body.hours,
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
    )
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
) -> None:
    _assert_path_matches_header(club_id)
    await service.confirm_booking(
        session, club_id=club_id, booking_id=booking_id, staff_id=context.current().user_id
    )


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
) -> None:
    _assert_path_matches_header(club_id)
    await service.reject_booking(
        session,
        club_id=club_id,
        booking_id=booking_id,
        staff_id=context.current().user_id,
        reason=body.reason,
    )
