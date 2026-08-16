"""Xarajatlar marshrutlari — `/api/v1/clubs/{club_id}/expenses`.

Faqat OWNER/ADMIN (`docs/01-architecture.md`:186 ruxsat matritsasi:
"Xarajatlar | ∑ | A | A | — | —" — STAFF chetda). `require_admin`
(OWNER+ADMIN) — `require_staff` EMAS, `pos/router.py`dagi mahsulot
o'qishidan farqi shu.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import Forbidden
from playbron.deps import db, require_admin, require_staff
from playbron.modules.finance import reports, service, shifts

router = APIRouter(prefix="/clubs", tags=["finance"])


def _assert_path_matches_header(club_id: int) -> None:
    """`pos/router.py`dagi bilan bir xil naqsh — yo'l va sarlavha klubi mos kelsin."""
    active = context.current().club_id
    if active is None or int(active) != int(club_id):
        raise Forbidden("Faol klub mos kelmadi", code="CLUB_MISMATCH")


class ExpenseOut(BaseModel):
    id: int
    spent_on: str
    category: str
    amount: int
    note: str | None
    status: str
    created_by_name: str | None
    created_at: str


class ExpenseCreateIn(BaseModel):
    spent_on: date
    category: str = Field(default="Boshqa", max_length=32)
    amount: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class ExpenseUpdateIn(BaseModel):
    spent_on: date
    category: str = Field(default="Boshqa", max_length=32)
    amount: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)
    status: str = Field(pattern="^(active|archived)$")


@router.get(
    "/{club_id}/expenses", response_model=list[ExpenseOut], dependencies=[Depends(require_admin)]
)
async def list_expenses(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[ExpenseOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_expenses(session, club_id)
    return [ExpenseOut(**r) for r in rows]


@router.post(
    "/{club_id}/expenses",
    response_model=ExpenseOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_expense(
    body: ExpenseCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ExpenseOut:
    _assert_path_matches_header(club_id)
    row = await service.create_expense(
        session,
        club_id=club_id,
        created_by=context.current().user_id,
        spent_on=body.spent_on,
        category=body.category,
        amount=body.amount,
        note=body.note,
    )
    return ExpenseOut(**row)


@router.patch(
    "/{club_id}/expenses/{expense_id}",
    response_model=ExpenseOut,
    dependencies=[Depends(require_admin)],
)
async def update_expense(
    body: ExpenseUpdateIn,
    club_id: Annotated[int, Path()],
    expense_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ExpenseOut:
    _assert_path_matches_header(club_id)
    row = await service.update_expense(
        session,
        club_id=club_id,
        expense_id=expense_id,
        spent_on=body.spent_on,
        category=body.category,
        amount=body.amount,
        note=body.note,
        status=body.status,
    )
    return ExpenseOut(**row)


# ── Smena ─────────────────────────────────────────────────────────────────
# Xodim (STAFF) o'z smenasini ochadi/yopadi — `require_staff` (OWNER/ADMIN
# ham kiradi, ular klubning BARCHA smenasini ko'radi/tuzatadi, RLS orqali).


class ShiftMovementOut(BaseModel):
    id: int
    kind: str
    amount: int
    reason: str
    created_by_name: str | None
    created_at: str


class ShiftOut(BaseModel):
    id: int
    staff_id: int
    opened_at: str
    opening_cash: int
    closed_at: str | None
    counted_cash: int | None
    status: str
    expected_cash: int
    variance: int | None
    movements: list[ShiftMovementOut]


class OpenShiftIn(BaseModel):
    opening_cash: int = Field(ge=0)


class ShiftMovementIn(BaseModel):
    kind: str = Field(pattern="^(IN|OUT)$")
    amount: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=300)


class CloseShiftIn(BaseModel):
    counted_cash: int = Field(ge=0)


class OpenShiftSummaryOut(BaseModel):
    id: int
    staff_id: int
    staff_name: str
    opened_at: str
    opening_cash: int


@router.get(
    "/{club_id}/shifts/current",
    response_model=ShiftOut | None,
    dependencies=[Depends(require_staff)],
)
async def current_shift(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> ShiftOut | None:
    _assert_path_matches_header(club_id)
    row = await shifts.get_current_shift(
        session, club_id=club_id, staff_id=context.current().user_id
    )
    return ShiftOut(**row) if row is not None else None


@router.get(
    "/{club_id}/shifts/open",
    response_model=list[OpenShiftSummaryOut],
    dependencies=[Depends(require_staff)],
)
async def open_shifts(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[OpenShiftSummaryOut]:
    """OWNER/ADMIN uchun klubdagi barcha ochiq smena; oddiy STAFF uchun RLS
    faqat o'zinikini qaytaradi — `dashboard.tsx` "Smenadagi xodimlar"."""
    _assert_path_matches_header(club_id)
    rows = await shifts.list_open_shifts(session, club_id)
    return [OpenShiftSummaryOut(**r) for r in rows]


@router.post(
    "/{club_id}/shifts",
    response_model=ShiftOut,
    status_code=201,
    dependencies=[Depends(require_staff)],
)
async def open_shift(
    body: OpenShiftIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ShiftOut:
    _assert_path_matches_header(club_id)
    row = await shifts.open_shift(
        session,
        club_id=club_id,
        staff_id=context.current().user_id,
        opening_cash=body.opening_cash,
    )
    return ShiftOut(**row)


@router.post(
    "/{club_id}/shifts/{shift_id}/movements",
    response_model=ShiftOut,
    status_code=201,
    dependencies=[Depends(require_staff)],
)
async def add_shift_movement(
    body: ShiftMovementIn,
    club_id: Annotated[int, Path()],
    shift_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ShiftOut:
    _assert_path_matches_header(club_id)
    row = await shifts.record_movement(
        session,
        club_id=club_id,
        shift_id=shift_id,
        kind=body.kind,
        amount=body.amount,
        reason=body.reason,
        created_by=context.current().user_id,
    )
    return ShiftOut(**row)


@router.post(
    "/{club_id}/shifts/{shift_id}/close",
    response_model=ShiftOut,
    dependencies=[Depends(require_staff)],
)
async def close_shift(
    body: CloseShiftIn,
    club_id: Annotated[int, Path()],
    shift_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ShiftOut:
    _assert_path_matches_header(club_id)
    row = await shifts.close_shift(
        session,
        club_id=club_id,
        shift_id=shift_id,
        counted_cash=body.counted_cash,
        closed_by=context.current().user_id,
    )
    return ShiftOut(**row)


# ── Boshqaruv paneli / Hisobot ───────────────────────────────────────────
# Faqat OWNER/ADMIN — `expenses`dagi bilan bir xil ruxsat, frontend nav'ida
# ham bu ekranlar faqat `NAV_ADMIN`da (STAFF'ga ko'rinmaydi).


class StationLiveOut(BaseModel):
    id: int
    code: str
    room_label: str
    # Band bo'lsa bronning konsoli, bo'sh yangi (konsolsiz) xonada `None`
    # (reja #38, `finance/reports.py::get_dashboard()`).
    console_type: str | None
    status: str
    occupied: bool


class DashboardOut(BaseModel):
    revenue_today: int
    expenses_today: int
    profit_today: int
    sessions_today: int
    hours_today: int
    occupancy_today: int
    bar_revenue_today: int
    opens_at_min: int
    closes_at_min: int
    hourly: dict[str, int]
    stations: list[StationLiveOut]


@router.get(
    "/{club_id}/dashboard", response_model=DashboardOut, dependencies=[Depends(require_admin)]
)
async def dashboard(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> DashboardOut:
    _assert_path_matches_header(club_id)
    row = await reports.get_dashboard(session, club_id)
    return DashboardOut(**{**row, "hourly": {str(k): v for k, v in row["hourly"].items()}})


class TopProductOut(BaseModel):
    product_name: str
    revenue: int


class ExpenseCategoryOut(BaseModel):
    category: str
    amount: int


class RevenueBucketOut(BaseModel):
    bucket: str
    amount: int


class ReportOut(BaseModel):
    period: str
    revenue: int
    expenses: int
    profit: int
    play_revenue: int
    bar_revenue: int
    sessions: int
    hours: int
    occupancy: int
    station_count: int
    top_products: list[TopProductOut]
    expense_by_category: list[ExpenseCategoryOut]
    revenue_series: list[RevenueBucketOut]


@router.get("/{club_id}/reports", response_model=ReportOut, dependencies=[Depends(require_admin)])
async def club_report(
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
    period: Literal["day", "week", "month", "year"] = "day",
) -> ReportOut:
    _assert_path_matches_header(club_id)
    row = await reports.get_report(session, club_id=club_id, period=period)
    return ReportOut(**row)
