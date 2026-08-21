"""Chek yakuni — sof hisob, DB'siz.

`CLAUDE.md` §Testlar: sof hisob funksiyasi DB'siz test bilan qoplanadi.
Bu modul `AsyncSession` bilmaydi: chaqiruvchi (`pos/service.py::close_bill`)
ma'lumotni o'qiydi, shu yerga uzatadi va natijani yozadi.

Invariant: `total = paid_amount + discount_amount + debt_amount − tip_amount`,
`discount_amount` va `debt_amount` bir vaqtda nolga teng bo'lmagan holda
uchramaydi, `tip_amount > 0` bo'lsa ikkalasi ham nol.

Testlar: `tests/test_money_pure.py` (`RUN_DB_TESTS`siz o'tadi).
"""

from dataclasses import dataclass

from playbron.core.errors import AppError


@dataclass(frozen=True, slots=True)
class BillSettlement:
    """Hisoblangan `total` bilan olingan summa farqining nomlangan taqsimoti."""

    discount_amount: int
    debt_amount: int
    tip_amount: int


def play_amount(rate_snapshot: int, hours: int) -> int:
    """O'yin summasi — hujjatga muhrlangan narx × soat.

    Narx joriy `stations.rate` dan emas, `bookings.rate_snapshot` dan
    (CLAUDE.md §Pul: yopilgan hujjat narxi qayta hisoblanmaydi).
    """
    return int(rate_snapshot) * int(hours)


def settle_bill(
    *,
    total: int,
    paid_amount: int,
    shortfall_reason: str | None,
    overpay_reason: str | None,
) -> BillSettlement:
    """Olingan summa bilan `total` farqini sababi bilan taqsimlaydi.

    Ortiqcha to'lov RAD ETILMAYDI. Mijoz 95 000 lik hisobga 100 000 berib
    qaytimni olmasa, xodim kassadagi HAQIQIY pulni yozishi kerak — aks holda
    u 95 000 deb ko'rsatishga majbur bo'lardi va smena aynan 5 000 ga
    "ortiq" chiqib, tushuntirib bo'lmas farq paydo bo'lardi. Sabab MAJBURIY:
    usiz 800 000 lik terish xatosi jimgina "choychaqa" bo'lib qolardi.

    Kam to'lov ham sababsiz qabul qilinmaydi: farq izsiz yo'qolmasligi uchun
    `DISCOUNT` (chegirma) yoki `DEBT` (qarz) tanlanadi
    (loyiha egasining qarori, 2026-08-17; `docs/audit-report.md` §2.2).
    """
    if paid_amount < 0:
        raise AppError("Summani tekshiring", code="PAID_AMOUNT_INVALID")

    shortfall = total - paid_amount

    tip_amount = 0
    if shortfall < 0:
        if overpay_reason != "TIP":
            raise AppError(
                "Hisobdan ortiq summa sababini tanlang",
                code="OVERPAY_REASON_REQUIRED",
                status_code=422,
            )
        tip_amount = -shortfall
        shortfall = 0

    discount_amount = 0
    debt_amount = 0
    if shortfall > 0:
        if shortfall_reason == "DISCOUNT":
            discount_amount = shortfall
        elif shortfall_reason == "DEBT":
            debt_amount = shortfall
        else:
            raise AppError(
                "Kam to'langan summaning sababini tanlang: chegirma yoki qarz",
                code="SHORTFALL_REASON_REQUIRED",
                status_code=422,
            )

    return BillSettlement(
        discount_amount=discount_amount,
        debt_amount=debt_amount,
        tip_amount=tip_amount,
    )
