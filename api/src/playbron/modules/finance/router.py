"""Xarajatlar marshrutlari — `/api/v1/clubs/{club_id}/expenses`.

Faqat OWNER/ADMIN (`docs/01-architecture.md`:186 ruxsat matritsasi:
"Xarajatlar | ∑ | A | A | — | —" — STAFF chetda). `require_admin`
(OWNER+ADMIN) — `require_staff` EMAS, `pos/router.py`dagi mahsulot
o'qishidan farqi shu.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import Forbidden
from playbron.deps import db, require_admin
from playbron.modules.finance import service

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
