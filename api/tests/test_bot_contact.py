"""Kontakt egaligi — oltita shartning har biri alohida.

Manba: `docs/05-auth-redesign.md` §4.2. Har bir test aniq bir hujumni
qulflaydi; bittasi tushib qolsa mijoz begona telefon raqami bilan
ro'yxatdan o'tadi.
"""

from typing import Any

import pytest

from playbron.modules.bot.contact import (
    REASON_BAD_PHONE,
    REASON_FOREIGN,
    REASON_FORWARDED,
    REASON_NO_CONTACT,
    REASON_NO_USER_ID,
    REASON_NOT_PRIVATE,
    REASON_VIA_BOT,
    check_contact,
    normalize_phone,
)

ME = 611_207_125
OTHER = 999_000_111


def message(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "from": {"id": ME},
        "chat": {"id": ME, "type": "private"},
        "contact": {"user_id": ME, "phone_number": "+998901234567"},
    }
    for key, value in over.items():
        if value is None:
            base.pop(key, None)
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = {**base[key], **value}
            base[key] = {k: v for k, v in merged.items() if v is not None}
        else:
            base[key] = value
    return base


def test_valid_contact_passes() -> None:
    result = check_contact(message())
    assert result.ok is True
    assert result.phone == "+998901234567"


def test_missing_contact() -> None:
    assert check_contact(message(contact=None)).reason == REASON_NO_CONTACT


def test_contact_without_user_id_is_rejected() -> None:
    """Telegram foydalanuvchisi bo'lmagan kontaktda `user_id` UMUMAN kelmaydi.

    Agar kod `contact.user_id != from.id` deb yozilganda edi, `None != 611…`
    → `True` bo'lib tekshiruv jimgina ochilib ketardi. Shuning uchun
    mavjudlik ALOHIDA tekshiriladi.
    """
    msg = message()
    msg["contact"].pop("user_id")
    assert check_contact(msg).reason == REASON_NO_USER_ID


def test_foreign_contact_from_address_book() -> None:
    """Address book'dan boshqa odamning raqamini ulashish."""
    assert check_contact(message(contact={"user_id": OTHER})).reason == REASON_FOREIGN


def test_group_chat_is_rejected() -> None:
    """Guruhda bot telefon yig'uvchi vositaga aylanmasin."""
    msg = message(chat={"id": -100_500, "type": "supergroup"})
    assert check_contact(msg).reason == REASON_NOT_PRIVATE


def test_private_chat_with_foreign_chat_id_is_rejected() -> None:
    assert check_contact(message(chat={"id": OTHER, "type": "private"})).reason == (
        REASON_NOT_PRIVATE
    )


def test_forwarded_message_is_rejected() -> None:
    assert check_contact(message(forward_origin={"type": "user"})).reason == REASON_FORWARDED
    assert check_contact(message(forward_from={"id": OTHER})).reason == REASON_FORWARDED


def test_via_bot_is_rejected() -> None:
    assert check_contact(message(via_bot={"id": 42})).reason == REASON_VIA_BOT


@pytest.mark.parametrize(
    "raw",
    [
        "+7 900 123 45 67",  # boshqa mamlakat
        "901234567",  # kod yo'q
        "+99890123456",  # kalta
        "+9989012345678",  # uzun
        "salom",
        "",
        None,
    ],
)
def test_bad_phone_is_rejected(raw: str | None) -> None:
    assert normalize_phone(raw) is None
    assert check_contact(message(contact={"phone_number": raw})).reason == REASON_BAD_PHONE


@pytest.mark.parametrize(
    ("raw", "expect"),
    [
        ("+998901234567", "+998901234567"),
        ("998901234567", "+998901234567"),  # Telegram `+` siz beradi
        ("+998 90 123 45 67", "+998901234567"),
        ("(998) 90-123-45-67", "+998901234567"),
    ],
)
def test_phone_normalization(raw: str, expect: str) -> None:
    assert normalize_phone(raw) == expect
