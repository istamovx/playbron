"""Telegram kontaktining egaligini tekshirish.

Manba: `docs/05-auth-redesign.md` §4.2 — dizayndagi eng muhim mijoz-tomon
nazorati. Oltita shartning bittasi tushib qolsa mijoz o'zini **begona telefon
raqami** bilan ro'yxatdan o'tkazadi va keyin o'sha raqam egasi kelganda hisob
allaqachon band bo'ladi.

Sof funksiya: tarmoq ham, DB ham yo'q — shuning uchun har bir shart alohida
sinaladi.
"""

import re
from dataclasses import dataclass
from typing import Any, Final

# Telegram `+` siz ham berishi mumkin
PHONE_RE: Final = re.compile(r"^\+998\d{9}$")
PHONE_MAX: Final = 20


# Rad etish sabablari — `auth_events` ga yoziladi (telefon raqamSIZ)
REASON_NO_CONTACT: Final = "no_contact"
REASON_NO_USER_ID: Final = "contact_without_user_id"
REASON_FOREIGN: Final = "foreign_contact"
REASON_NOT_PRIVATE: Final = "not_private_chat"
REASON_FORWARDED: Final = "forwarded"
REASON_VIA_BOT: Final = "via_bot"
REASON_BAD_PHONE: Final = "bad_phone"


@dataclass(slots=True, frozen=True)
class ContactCheck:
    ok: bool
    phone: str | None = None
    reason: str | None = None


def normalize_phone(raw: str | None) -> str | None:
    """E.164 `+998XXXXXXXXX`. Mos kelmasa `None`.

    Uzunlik `users.phone` (`String(20)`) ga sig'ishi SHU YERDA tekshiriladi —
    DB xatosi bilan emas.
    """
    if not raw:
        return None

    digits = "".join(ch for ch in raw if ch.isdigit())
    candidate = f"+{digits}"

    if len(candidate) > PHONE_MAX:
        return None
    if not PHONE_RE.match(candidate):
        return None
    return candidate


def check_contact(message: dict[str, Any]) -> ContactCheck:
    """Oltita shart. Hammasi majburiy, tartibi ahamiyatsiz."""
    contact = message.get("contact")
    if not isinstance(contact, dict):
        return ContactCheck(ok=False, reason=REASON_NO_CONTACT)

    sender = message.get("from") or {}
    sender_id = sender.get("id")

    # 1. `user_id` MAVJUDLIGI alohida tekshiriladi. Telegram foydalanuvchisi
    #    bo'lmagan kontaktda bu maydon umuman kelmaydi va `contact.user_id !=
    #    from.id` deb yozilsa `None != 12345` → True bo'lib, tekshiruv jimgina
    #    ochilib ketardi.
    contact_user_id = contact.get("user_id")
    if contact_user_id is None:
        return ContactCheck(ok=False, reason=REASON_NO_USER_ID)

    # 2. Address book'dan ulashilgan begona kontakt
    if int(contact_user_id) != int(sender_id or 0):
        return ContactCheck(ok=False, reason=REASON_FOREIGN)

    # 3. Faqat shaxsiy chat: guruhda bot telefon yig'uvchi vositaga aylanmasin
    #    va javob matni begonalarga ko'rinmasin
    chat = message.get("chat") or {}
    if chat.get("type") != "private" or int(chat.get("id") or 0) != int(sender_id or 0):
        return ContactCheck(ok=False, reason=REASON_NOT_PRIVATE)

    # 4. Uzatilgan xabar
    if message.get("forward_origin") or message.get("forward_from"):
        return ContactCheck(ok=False, reason=REASON_FORWARDED)

    # 5. Boshqa bot orqali kelgan
    if message.get("via_bot"):
        return ContactCheck(ok=False, reason=REASON_VIA_BOT)

    # 6-shart (`awaiting_contact` holatining atomik iste'moli) chaqiruvchida:
    #    u Redis'ga tegadi va sof funksiyada bo'lolmaydi.

    phone = normalize_phone(contact.get("phone_number"))
    if phone is None:
        return ContactCheck(ok=False, reason=REASON_BAD_PHONE)

    return ContactCheck(ok=True, phone=phone)
