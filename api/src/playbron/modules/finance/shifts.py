"""Smena — xodim kassa ochish/yopish, qo'lda kirim/chiqim.

Manba: `api/migrations/versions/0021_shifts.py`. RLS defense-in-depth —
bu yerdagi tekshiruvlar HAKAM emas, ikkinchi qatlam.

"Kutilayotgan naqd" — `opening_cash` + qo'lda kirim/chiqim + shu smena
davomida NAQD yopilgan bronlar yig'indisi (`bookings.paid_amount`,
`0013_pos.py`dan bor — bu yerda TAKRORLANMAYDI, faqat o'qiladi).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.audit import log_action
from playbron.core.errors import AppError, NotFound

REASON_MAX = 300


async def _load_shift(session: AsyncSession, club_id: int, shift_id: int) -> Any:
    row = (
        await session.execute(
            text(
                "SELECT id, staff_id, opened_at, opening_cash, closed_at, counted_cash, status"
                " FROM shifts WHERE id = :id AND club_id = :club_id"
            ),
            {"id": shift_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Smena topilmadi")
    return row


async def _expected_cash(session: AsyncSession, *, club_id: int, shift: Any) -> int:
    movements_total = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(CASE WHEN kind = 'IN' THEN amount ELSE -amount END), 0)"
                " FROM shift_cash_movements WHERE shift_id = :id"
            ),
            {"id": shift.id},
        )
    ).scalar_one()

    cash_bills_total = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(paid_amount), 0) FROM bookings"
                " WHERE club_id = :club_id AND closed_by = :staff AND payment_method = 'CASH'"
                "   AND closed_at BETWEEN :opened AND :until"
            ),
            {
                "club_id": club_id,
                "staff": shift.staff_id,
                "opened": shift.opened_at,
                "until": shift.closed_at or datetime.now(UTC),
            },
        )
    ).scalar_one()

    return int(shift.opening_cash) + int(movements_total) + int(cash_bills_total)


def _movement_row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "amount": int(row.amount),
        "reason": row.reason,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat(),
    }


async def _list_movements(session: AsyncSession, shift_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT m.id, m.kind, m.amount, m.reason, m.created_at,"
                "       u.first_name AS created_by_name"
                " FROM shift_cash_movements m LEFT JOIN users u ON u.id = m.created_by"
                " WHERE m.shift_id = :id ORDER BY m.created_at DESC"
            ),
            {"id": shift_id},
        )
    ).all()
    return [_movement_row(r) for r in rows]


async def _shift_detail(session: AsyncSession, *, club_id: int, shift: Any) -> dict[str, Any]:
    expected = await _expected_cash(session, club_id=club_id, shift=shift)
    movements = await _list_movements(session, shift.id)
    variance = None if shift.counted_cash is None else int(shift.counted_cash) - expected
    return {
        "id": shift.id,
        "staff_id": shift.staff_id,
        "opened_at": shift.opened_at.isoformat(),
        "opening_cash": int(shift.opening_cash),
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "counted_cash": int(shift.counted_cash) if shift.counted_cash is not None else None,
        "status": shift.status,
        "expected_cash": expected,
        "variance": variance,
        "movements": movements,
    }


async def get_current_shift(
    session: AsyncSession, *, club_id: int, staff_id: int
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                "SELECT id, staff_id, opened_at, opening_cash, closed_at, counted_cash, status"
                " FROM shifts WHERE club_id = :club_id AND staff_id = :staff AND status = 'open'"
            ),
            {"club_id": club_id, "staff": staff_id},
        )
    ).first()
    if row is None:
        return None
    return await _shift_detail(session, club_id=club_id, shift=row)


async def list_open_shifts(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Klubdagi HOZIR ochiq barcha smenalar — OWNER/ADMIN uchun to'liq,
    oddiy STAFF uchun RLS faqat o'zinikini qaytaradi (`dashboard.tsx`
    "Smenadagi xodimlar" paneli shu yerdan)."""
    rows = (
        await session.execute(
            text(
                "SELECT s.id, s.staff_id, s.opened_at, s.opening_cash,"
                "       u.first_name AS staff_name"
                " FROM shifts s JOIN users u ON u.id = s.staff_id"
                " WHERE s.club_id = :club_id AND s.status = 'open'"
                " ORDER BY s.opened_at"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        {
            "id": r.id,
            "staff_id": r.staff_id,
            "staff_name": r.staff_name,
            "opened_at": r.opened_at.isoformat(),
            "opening_cash": int(r.opening_cash),
        }
        for r in rows
    ]


async def open_shift(
    session: AsyncSession, *, club_id: int, staff_id: int, opening_cash: int
) -> dict[str, Any]:
    if opening_cash < 0:
        raise AppError("Boshlang'ich kassa manfiy bo'lmasin", code="OPENING_CASH_INVALID")

    try:
        shift_id = await session.scalar(
            text(
                "INSERT INTO shifts (club_id, staff_id, opening_cash)"
                " VALUES (:club_id, :staff, :cash) RETURNING id"
            ),
            {"club_id": club_id, "staff": staff_id, "cash": opening_cash},
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "23505":
            raise AppError(
                "Sizda allaqachon ochiq smena bor", code="SHIFT_ALREADY_OPEN", status_code=409
            ) from exc
        raise

    await log_action(
        action="shift_opened",
        target=str(shift_id),
        club_id=club_id,
        after={"opening_cash": opening_cash},
    )

    shift = await _load_shift(session, club_id, shift_id)
    return await _shift_detail(session, club_id=club_id, shift=shift)


async def record_movement(
    session: AsyncSession,
    *,
    club_id: int,
    shift_id: int,
    kind: str,
    amount: int,
    reason: str,
    created_by: int,
) -> dict[str, Any]:
    if kind not in ("IN", "OUT"):
        raise AppError("Noma'lum harakat turi", code="KIND_INVALID")
    if amount <= 0:
        raise AppError("Summa musbat bo'lsin", code="AMOUNT_INVALID")
    reason = reason.strip()[:REASON_MAX]
    if not reason:
        raise AppError("Sababni kiriting", code="REASON_REQUIRED")

    shift = await _load_shift(session, club_id, shift_id)
    if shift.status != "open":
        raise AppError("Smena allaqachon yopilgan", code="SHIFT_CLOSED", status_code=409)

    await session.execute(
        text(
            "INSERT INTO shift_cash_movements (club_id, shift_id, kind, amount, reason, created_by)"
            " VALUES (:club_id, :shift_id, :kind, :amount, :reason, :created_by)"
        ),
        {
            "club_id": club_id,
            "shift_id": shift_id,
            "kind": kind,
            "amount": amount,
            "reason": reason,
            "created_by": created_by,
        },
    )

    await log_action(
        action="shift_cash_in" if kind == "IN" else "shift_cash_out",
        target=reason,
        club_id=club_id,
        after={"shift_id": shift_id, "amount": amount},
    )

    shift = await _load_shift(session, club_id, shift_id)
    return await _shift_detail(session, club_id=club_id, shift=shift)


async def close_shift(
    session: AsyncSession, *, club_id: int, shift_id: int, counted_cash: int, closed_by: int
) -> dict[str, Any]:
    if counted_cash < 0:
        raise AppError("Sanalgan summa manfiy bo'lmasin", code="COUNTED_CASH_INVALID")

    shift = await _load_shift(session, club_id, shift_id)
    if shift.status != "open":
        raise AppError("Smena allaqachon yopilgan", code="SHIFT_CLOSED", status_code=409)

    await session.execute(
        text(
            "UPDATE shifts SET status = 'closed', closed_at = :now, counted_cash = :counted,"
            " closed_by = :by WHERE id = :id"
        ),
        {"now": datetime.now(UTC), "counted": counted_cash, "by": closed_by, "id": shift_id},
    )

    shift = await _load_shift(session, club_id, shift_id)
    detail = await _shift_detail(session, club_id=club_id, shift=shift)

    await log_action(
        action="shift_closed",
        target=str(shift_id),
        club_id=club_id,
        after={"counted_cash": counted_cash, "variance": detail["variance"]},
    )

    return detail
