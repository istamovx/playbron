"""Xarajatlar — klub darajasidagi qo'lda kiritiladigan xarajat qatorlari.

Manba: `api/migrations/versions/0020_expenses.py`. RLS defense-in-depth —
bu yerdagi tekshiruvlar HAKAM emas, ikkinchi qatlam (`pos/service.py`dagi
bilan bir xil falsafa).

`status='archived'` — yagona "o'chirish" yo'li, `products`dagi bilan bir
xil naqsh: qator hech qachon jismoniy o'chmaydi (`APP_ROLE`ga DELETE
GRANT umuman berilmagan, `0020`).
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.audit import log_action
from playbron.core.errors import AppError, NotFound
from playbron.core.text import clean_name
from playbron.modules.finance import shifts

CATEGORY_MAX = 32
NOTE_MAX = 500


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "spent_on": row.spent_on.isoformat(),
        "category": row.category,
        "amount": int(row.amount),
        "note": row.note,
        "status": row.status,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat(),
        "method": row.method,
    }


async def list_expenses(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Faol VA arxivlangan — `products`dagi bilan bir xil: tarix yo'qolmaydi,
    UI `Holat` ustunida ko'rsatadi (frontend, kerak bo'lsa, filtrlaydi)."""
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.spent_on, e.category, e.amount, e.note, e.status, e.created_at,"
                "       e.method, u.first_name AS created_by_name"
                " FROM expenses e LEFT JOIN users u ON u.id = e.created_by"
                " WHERE e.club_id = :club_id"
                " ORDER BY e.spent_on DESC, e.id DESC"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_row(r) for r in rows]


async def create_expense(
    session: AsyncSession,
    *,
    club_id: int,
    created_by: int,
    spent_on: date,
    category: str,
    amount: int,
    note: str | None,
    method: str | None = None,
    shift_id: int | None = None,
) -> dict[str, Any]:
    category = clean_name(category, limit=CATEGORY_MAX) or "Boshqa"
    if amount <= 0:
        raise AppError("Summa musbat bo'lsin", code="AMOUNT_INVALID")
    if method is not None and method not in ("CASH", "TRANSFER"):
        raise AppError("To'lov turi noto'g'ri", code="PAYMENT_METHOD_INVALID")
    note = (note or "").strip()[:NOTE_MAX] or None

    # Naqd xarajat kassadan chiqadi — shuning uchun u ochiq smenaga
    # bog'lanadi (`docs/audit-report.md` §2.3). Smena yo'q bo'lsa naqd
    # xarajat qabul qilinmaydi: aks holda kassa farqi tushuntirib
    # bo'lmaydigan bo'lib qolardi.
    # Kim yozayotgani bilan kassani KIM ushlab turgani ko'pincha BOSHQA
    # odam: xarajat endpointi `require_admin`, smena esa STAFF'niki.
    # Shuning uchun `shift_id` ochiq tanlanadi; berilmasa yozayotganning
    # o'z smenasiga tushadi.
    if method == "CASH":
        if shift_id is None:
            shift_id = await shifts.open_shift_id(
                session, club_id=club_id, staff_id=created_by
            )
        elif not await shifts.shift_is_open(session, club_id=club_id, shift_id=shift_id):
            raise AppError(
                "Smena topilmadi yoki allaqachon yopilgan",
                code="SHIFT_NOT_OPEN",
                status_code=409,
            )
        if shift_id is None:
            raise AppError(
                "Naqd xarajat qaysi smenadan chiqqanini tanlang",
                code="SHIFT_REQUIRED",
                status_code=409,
            )
    else:
        # Naqd bo'lmagan xarajat kassaga tegmaydi — smenaga ham bog'lanmaydi.
        shift_id = None

    row = (
        await session.execute(
            text(
                "INSERT INTO expenses"
                " (club_id, spent_on, category, amount, note, created_by, method, shift_id)"
                " VALUES (:club_id, :spent_on, :category, :amount, :note, :created_by,"
                "         :method, :shift_id)"
                " RETURNING id, spent_on, category, amount, note, status, created_at, method"
            ),
            {
                "club_id": club_id,
                "spent_on": spent_on,
                "category": category,
                "amount": amount,
                "note": note,
                "created_by": created_by,
                "method": method,
                "shift_id": shift_id,
            },
        )
    ).first()
    assert row is not None  # INSERT ... RETURNING — muvaffaqiyatsiz bo'lsa istisno tashlaydi

    await log_action(
        action="expense_created",
        target=category,
        club_id=club_id,
        after={"spent_on": spent_on.isoformat(), "category": category, "amount": amount},
    )

    return {
        "id": row.id,
        "spent_on": row.spent_on.isoformat(),
        "category": row.category,
        "amount": int(row.amount),
        "note": row.note,
        "status": row.status,
        "created_by_name": None,  # hozirgina yaratildi — kiritgan kishi allaqachon actor
        "created_at": row.created_at.isoformat(),
        "method": row.method,
    }


async def update_expense(
    session: AsyncSession,
    *,
    club_id: int,
    expense_id: int,
    spent_on: date,
    category: str,
    amount: int,
    note: str | None,
    status: str,
) -> dict[str, Any]:
    category = clean_name(category, limit=CATEGORY_MAX) or "Boshqa"
    if amount <= 0:
        raise AppError("Summa musbat bo'lsin", code="AMOUNT_INVALID")
    if status not in ("active", "archived"):
        raise AppError("Noma'lum holat", code="STATUS_INVALID")
    note = (note or "").strip()[:NOTE_MAX] or None

    # Yopilgan smenaga bog'langan naqd xarajat O'ZGARMAYDI. `_expected_cash()`
    # har o'qishda QAYTA hisoblaydi — ya'ni bunday tahrir allaqachon
    # yopilgan smenaning "kutilayotgan naqd"ini va farqini RETROAKTIV
    # o'zgartirardi va audit jurnalidagi yozuv bilan ziddiyatga tushardi.
    linked = (
        await session.execute(
            text(
                "SELECT s.status FROM expenses e JOIN shifts s ON s.id = e.shift_id"
                " WHERE e.id = :id AND e.club_id = :club_id"
            ),
            {"id": expense_id, "club_id": club_id},
        )
    ).first()
    if linked is not None and linked.status == "closed":
        raise AppError(
            "Yopilgan smenaga tegishli xarajat o'zgartirilmaydi",
            code="SHIFT_CLOSED",
            status_code=409,
        )

    row = (
        await session.execute(
            text(
                "UPDATE expenses SET spent_on = :spent_on, category = :category,"
                " amount = :amount, note = :note, status = :status"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id"
            ),
            {
                "spent_on": spent_on,
                "category": category,
                "amount": amount,
                "note": note,
                "status": status,
                "id": expense_id,
                "club_id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Xarajat topilmadi")

    await log_action(
        action="expense_updated" if status == "active" else "expense_archived",
        target=category,
        club_id=club_id,
        after={
            "spent_on": spent_on.isoformat(),
            "category": category,
            "amount": amount,
            "status": status,
        },
    )

    full = (
        await session.execute(
            text(
                "SELECT e.id, e.spent_on, e.category, e.amount, e.note, e.status, e.created_at,"
                "       e.method, u.first_name AS created_by_name"
                " FROM expenses e LEFT JOIN users u ON u.id = e.created_by"
                " WHERE e.id = :id"
            ),
            {"id": expense_id},
        )
    ).first()
    assert full is not None
    return _row(full)
