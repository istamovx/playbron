"""Pul hisobining sof funksiyalari — DB'SIZ, `RUN_DB_TESTS`siz o'tadi.

    cd api && python -m pytest tests/test_money_pure.py -q

`CLAUDE.md` §Testlar: sof hisob funksiyasi DB'siz test bilan qoplanadi.
Kutilgan sonlar qo'lda hisoblangan — funksiya natijasidan ko'chirilmagan.
"""

import pytest

from playbron.core.errors import AppError
from playbron.modules.finance.cash import cash_variance, expected_cash
from playbron.modules.pos.settlement import BillSettlement, play_amount, settle_bill

# ── play_amount ───────────────────────────────────────────────────────────


def test_play_amount_is_rate_times_hours() -> None:
    # 40 000 so'm/soat × 2 soat = 80 000
    assert play_amount(40_000, 2) == 80_000


def test_play_amount_zero_hours_is_zero() -> None:
    assert play_amount(40_000, 0) == 0


# ── settle_bill: aniq to'lov ──────────────────────────────────────────────


def test_exact_payment_has_no_difference() -> None:
    result = settle_bill(
        total=100_000, paid_amount=100_000, shortfall_reason=None, overpay_reason=None
    )
    assert result == BillSettlement(discount_amount=0, debt_amount=0, tip_amount=0)


def test_zero_total_zero_paid() -> None:
    result = settle_bill(total=0, paid_amount=0, shortfall_reason=None, overpay_reason=None)
    assert result == BillSettlement(discount_amount=0, debt_amount=0, tip_amount=0)


# ── settle_bill: kam to'lov ───────────────────────────────────────────────


def test_full_discount_covers_whole_total() -> None:
    # Hech narsa to'lanmadi, hammasi chegirma: discount == total
    result = settle_bill(
        total=80_000, paid_amount=0, shortfall_reason="DISCOUNT", overpay_reason=None
    )
    assert result == BillSettlement(discount_amount=80_000, debt_amount=0, tip_amount=0)


def test_partial_payment_becomes_debt() -> None:
    # 120 000 dan 90 000 to'landi — 30 000 qarz
    result = settle_bill(
        total=120_000, paid_amount=90_000, shortfall_reason="DEBT", overpay_reason=None
    )
    assert result == BillSettlement(discount_amount=0, debt_amount=30_000, tip_amount=0)


def test_shortfall_without_reason_is_rejected() -> None:
    with pytest.raises(AppError) as err:
        settle_bill(total=50_000, paid_amount=40_000, shortfall_reason=None, overpay_reason=None)
    assert err.value.code == "SHORTFALL_REASON_REQUIRED"
    assert err.value.status_code == 422


def test_shortfall_with_unknown_reason_is_rejected() -> None:
    # Sabab ro'yxatdan tashqarida — xuddi sababsiz kabi rad etiladi
    with pytest.raises(AppError) as err:
        settle_bill(total=50_000, paid_amount=40_000, shortfall_reason="TIP", overpay_reason=None)
    assert err.value.code == "SHORTFALL_REASON_REQUIRED"


# ── settle_bill: ortiqcha to'lov ──────────────────────────────────────────


def test_overpayment_becomes_tip() -> None:
    # 95 000 lik hisobga 100 000 — 5 000 choychaqa
    result = settle_bill(
        total=95_000, paid_amount=100_000, shortfall_reason=None, overpay_reason="TIP"
    )
    assert result == BillSettlement(discount_amount=0, debt_amount=0, tip_amount=5_000)


def test_overpayment_without_reason_is_rejected() -> None:
    with pytest.raises(AppError) as err:
        settle_bill(total=95_000, paid_amount=100_000, shortfall_reason=None, overpay_reason=None)
    assert err.value.code == "OVERPAY_REASON_REQUIRED"
    assert err.value.status_code == 422


def test_negative_paid_amount_is_rejected() -> None:
    with pytest.raises(AppError) as err:
        settle_bill(total=10_000, paid_amount=-1, shortfall_reason=None, overpay_reason=None)
    assert err.value.code == "PAID_AMOUNT_INVALID"


# ── settle_bill: invariantlar ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("total", "paid", "shortfall_reason", "overpay_reason"),
    [
        (100_000, 100_000, None, None),
        (80_000, 0, "DISCOUNT", None),
        (120_000, 90_000, "DEBT", None),
        (95_000, 100_000, None, "TIP"),
        (0, 0, None, None),
    ],
)
def test_settlement_balances_the_equation(
    total: int, paid: int, shortfall_reason: str | None, overpay_reason: str | None
) -> None:
    """`total = paid + discount + debt − tip` — har qanday yo'lda."""
    s = settle_bill(
        total=total,
        paid_amount=paid,
        shortfall_reason=shortfall_reason,
        overpay_reason=overpay_reason,
    )
    assert total == paid + s.discount_amount + s.debt_amount - s.tip_amount
    # Chegirma bilan qarz bir vaqtda uchramaydi
    assert s.discount_amount == 0 or s.debt_amount == 0
    # Choychaqa bo'lsa kam to'lov bo'lishi mumkin emas
    if s.tip_amount > 0:
        assert s.discount_amount == 0 and s.debt_amount == 0


# ── expected_cash ─────────────────────────────────────────────────────────


def test_expected_cash_sums_all_components() -> None:
    # 500 000 ochilish + 50 000 harakat (200k IN − 150k OUT)
    # + 300 000 naqd kirim − 40 000 qaytarim − 60 000 xarajat = 750 000
    assert (
        expected_cash(
            opening_cash=500_000,
            movements_total=50_000,
            cash_in=300_000,
            cash_refunds=40_000,
            cash_expenses=60_000,
        )
        == 750_000
    )


def test_expected_cash_with_no_activity_is_opening_cash() -> None:
    assert (
        expected_cash(
            opening_cash=200_000, movements_total=0, cash_in=0, cash_refunds=0, cash_expenses=0
        )
        == 200_000
    )


def test_refund_returns_the_till_to_start() -> None:
    # Sotuv 100 000, keyin to'liq qaytarim — kassa boshlang'ich holatga qaytadi
    assert (
        expected_cash(
            opening_cash=0, movements_total=0, cash_in=100_000, cash_refunds=100_000,
            cash_expenses=0,
        )
        == 0
    )


def test_out_movements_reduce_expected_cash() -> None:
    # Faqat 70 000 chiqim: 300 000 − 70 000 = 230 000
    assert (
        expected_cash(
            opening_cash=300_000, movements_total=-70_000, cash_in=0, cash_refunds=0,
            cash_expenses=0,
        )
        == 230_000
    )


# ── cash_variance ─────────────────────────────────────────────────────────


def test_variance_is_none_until_counted() -> None:
    assert cash_variance(None, 750_000) is None


def test_variance_zero_when_counts_match() -> None:
    assert cash_variance(750_000, 750_000) == 0


def test_variance_positive_when_till_has_extra() -> None:
    assert cash_variance(760_000, 750_000) == 10_000


def test_variance_negative_when_till_is_short() -> None:
    assert cash_variance(700_000, 750_000) == -50_000
