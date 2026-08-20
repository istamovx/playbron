"""Kassa hisobi — sof funksiyalar, DB'siz.

`CLAUDE.md` §Testlar: sof hisob funksiyasi DB'siz test bilan qoplanadi.
Chaqiruvchi (`finance/shifts.py`) yig'indilarni SQL bilan o'qiydi va shu
yerga uzatadi — formula bitta joyda turadi.

Testlar: `tests/test_money_pure.py` (`RUN_DB_TESTS`siz o'tadi).
"""


def expected_cash(
    *,
    opening_cash: int,
    movements_total: int,
    cash_in: int,
    cash_refunds: int,
    cash_expenses: int,
) -> int:
    """Kutilayotgan naqd:

    `opening_cash + movements ± + payments(CASH, FINAL) − payments(CASH,
    REFUND) − expenses(CASH, active)`.

    `movements_total` — `IN` musbat, `OUT` manfiy holda kelgan yig'indi.
    """
    return (
        int(opening_cash)
        + int(movements_total)
        + int(cash_in)
        - int(cash_refunds)
        - int(cash_expenses)
    )


def cash_variance(counted_cash: int | None, expected: int) -> int | None:
    """Sanalgan naqd bilan kutilgan naqd farqi.

    Smena hali sanalmagan (`counted_cash IS NULL`) bo'lsa farq ham yo'q.
    Farq SAQLANMAYDI — har o'qishda qayta hisoblanadi (CLAUDE.md §Pul:
    hisob bitta manbadan).
    """
    return None if counted_cash is None else int(counted_cash) - int(expected)
