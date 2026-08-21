"""Xodim chegirmasining chegarasi — sof funksiya, DB'siz va PostgreSQL'siz.

`CLAUDE.md`, «Testlar»: sof hisob funksiyasi DB'siz test bilan qoplanadi.
Bu fayl `RUN_DB_TESTS` ga bog'liq emas.

Qoplanadigan teshik (rol auditi, 2026-08-18): `STAFF` roli
`paid_amount = 0` + `shortfall_reason = 'DISCOUNT'` bilan istalgan
hisobni to'liq nolga yopa olardi.
"""

import pytest

from playbron.core.errors import AppError
from playbron.modules.pos.service import _assert_discount_allowed

TOTAL = 80_000
LIMIT = 20  # `clubs.staff_max_discount_percent` sukuti


def _call(role: str | None, discount: int, total: int = TOTAL, limit: int = LIMIT) -> None:
    _assert_discount_allowed(
        actor_role=role,
        discount_amount=discount,
        total=total,
        limit_percent=limit,
    )


@pytest.mark.parametrize(
    ("role", "discount"),
    [
        # Aynan chegarada — 16 000 = 80 000 ning 20% i
        ("STAFF", 16_000),
        ("STAFF", 1),
        # Chegirma umuman yo'q
        ("STAFF", 0),
        (None, 0),
        # Ega va admin chegaradan TASHQARIDA — chegirma ularning qarori
        ("OWNER", TOTAL),
        ("ADMIN", TOTAL),
    ],
)
def test_allowed(role: str | None, discount: int) -> None:
    _call(role, discount)


@pytest.mark.parametrize(
    ("role", "discount"),
    [
        # 20 000 = 25% — chegaradan bir qadam yuqori
        ("STAFF", 20_000),
        # To'liq nolga yopish — auditda topilgan asl teshik
        ("STAFF", TOTAL),
        # Rol noma'lum: eng qattiq yo'l tanlanadi. Teskarisi yozilsa,
        # klaymi buzilgan chaqiruv jimgina cheklovsiz o'tib ketardi.
        (None, 20_000),
        ("", 20_000),
        # Yaqin, lekin baribir yuqori — foiz butun songa yaxlitlanmaydi
        ("STAFF", 16_001),
    ],
)
def test_rejected(role: str | None, discount: int) -> None:
    with pytest.raises(AppError) as exc:
        _call(role, discount)
    assert exc.value.code == "DISCOUNT_LIMIT_EXCEEDED"
    assert exc.value.status_code == 422


def test_zero_total_blocks_any_staff_discount() -> None:
    """`total = 0` da foizga bo'lish mumkin emas — aniq taqqoslash kerak."""
    with pytest.raises(AppError):
        _call("STAFF", 1, total=0, limit=100)


def test_limit_zero_blocks_every_staff_discount() -> None:
    """Klub xodimga chegirmani UMUMAN taqiqlashi mumkin — `0` chegarasi."""
    with pytest.raises(AppError):
        _call("STAFF", 1, limit=0)
    # Ega baribir bera oladi
    _call("OWNER", TOTAL, limit=0)


def test_limit_hundred_allows_full_discount() -> None:
    """Teskari uchi: klub xodimga to'liq erkinlik berishi ham mumkin."""
    _call("STAFF", TOTAL, limit=100)
