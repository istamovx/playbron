"""Telegram imzosini tekshirish — ikki kanal, bitta natija.

  • Login Widget (landing, brauzer)
  • Mini App `initData` (Telegram ichida)

Ikkalasi ham `data_check_string` + HMAC-SHA256 sxemasidan foydalanadi, lekin
**kalit hosil qilish tartibi har xil**.

╔═══════════════════════════════════════════════════════════════════════════╗
║ [TEKSHIRISH] — ishlab chiqarishga chiqishdan oldin majburiy               ║
║                                                                           ║
║ Quyidagi ikki qator rasmiy hujjat bilan solishtirilsin:                   ║
║   1. Login Widget  → Telegram docs: "Login Widget / Checking              ║
║      authorization"                                                       ║
║   2. Mini App      → Telegram docs: "Mini Apps / Validating data          ║
║      received via the Mini App"                                           ║
║                                                                           ║
║ Tekshirilishi kerak:                                                      ║
║   • kalit qaysi tomonda (`key`, `msg`) turishi                            ║
║   • `WebAppData` konstantasining aniq yozilishi                           ║
║   • `data_check_string` da qaysi maydonlar qatnashishi                    ║
║   • yangi `signature` (Ed25519) maydoni majburiymi                        ║
║                                                                           ║
║ Kod o'zi bilan izchil (`tests/test_telegram_auth.py`), lekin bu Telegram  ║
║ bilan mosligini isbotlamaydi — haqiqiy `initData` namunasi bilan test     ║
║ qilinishi shart.                                                          ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

from playbron.core.config import settings
from playbron.core.errors import Unauthorized
from playbron.core.security import constant_time_equal, now

WEBAPP_CONSTANT = b"WebAppData"


@dataclass(slots=True)
class TelegramIdentity:
    """Imzosi tekshirilgan Telegram foydalanuvchisi."""

    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    photo_url: str | None
    auth_date: int
    raw_hash: str
    source: str  # "initdata" | "widget"


def _data_check_string(fields: dict[str, str]) -> str:
    """`hash` dan tashqari barcha maydon alifbo tartibida `k=v\\n` ko'rinishida."""
    return "\n".join(f"{key}={fields[key]}" for key in sorted(fields) if key != "hash")


def _hmac_hex(key: bytes, message: str) -> str:
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def _check_age(auth_date: int, ttl_sec: int) -> None:
    age = int(now().timestamp()) - auth_date
    if age < -60:  # kelajakdagi sana — soat siljigan yoki soxta
        raise Unauthorized("auth_date noto‘g‘ri", code="AUTH_DATE_INVALID")
    if age > ttl_sec:
        raise Unauthorized("Imzo muddati tugagan", code="AUTH_DATE_EXPIRED")


def _bot_token() -> str:
    """Mini App tokeni — mijoz yuzasi `@playbronbot` ga tegishli."""
    token = settings.bot_token.get_secret_value()
    if not token:
        raise Unauthorized("Bot token sozlanmagan", code="BOT_NOT_CONFIGURED")
    return token


def _widget_token() -> str:
    """Login Widget tokeni.

    Widget klub egasi va xodim uchun — u **admin bot** (`@playbronappbot`)
    orqali ishlaydi, chunki konsolga kirish mijoz oqimidan ajratilgan.
    Asosiy botga qaytish faqat lokal muhit uchun: prod'da `ADMIN_BOT_TOKEN`
    config tomonidan majburiy qilinadi (aks holda imzo doim mos kelmasdi).
    """
    token = settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()
    if not token:
        raise Unauthorized("Bot token sozlanmagan", code="BOT_NOT_CONFIGURED")
    return token


def verify_init_data(init_data: str) -> TelegramIdentity:
    """Mini App `window.Telegram.WebApp.initData` ni tekshiradi.

    `init_data` — query-string ko'rinishidagi satr.
    """
    if not init_data:
        raise Unauthorized("initData bo‘sh", code="INITDATA_MISSING")

    fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = fields.get("hash")
    if not received:
        raise Unauthorized("initData imzosi yo‘q", code="INITDATA_NO_HASH")

    # [TEKSHIRISH] Mini App: kalit — bot tokenidan `WebAppData` konstantasi bilan
    secret_key = hmac.new(WEBAPP_CONSTANT, _bot_token().encode(), hashlib.sha256).digest()
    expected = _hmac_hex(secret_key, _data_check_string(fields))

    if not constant_time_equal(expected, received):
        raise Unauthorized("initData imzosi mos kelmadi", code="INITDATA_BAD_SIGNATURE")

    auth_date = int(fields.get("auth_date", "0"))
    _check_age(auth_date, settings.initdata_ttl_sec)

    user_raw = fields.get("user")
    if not user_raw:
        raise Unauthorized("initData'da user yo‘q", code="INITDATA_NO_USER")

    try:
        user: dict[str, Any] = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise Unauthorized("initData'dagi user buzilgan", code="INITDATA_BAD_USER") from exc

    return TelegramIdentity(
        telegram_id=int(user["id"]),
        first_name=str(user.get("first_name") or ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        language_code=user.get("language_code"),
        photo_url=user.get("photo_url"),
        auth_date=auth_date,
        raw_hash=received,
        source="initdata",
    )


def verify_widget(payload: dict[str, Any]) -> TelegramIdentity:
    """Landing'dagi Telegram Login Widget javobini tekshiradi.

    `payload` — widget qaytargan tekis obyekt: id, first_name, auth_date, hash, …
    """
    fields = {key: str(value) for key, value in payload.items() if value is not None}
    received = fields.get("hash")
    if not received:
        raise Unauthorized("Widget imzosi yo‘q", code="WIDGET_NO_HASH")

    # [TEKSHIRISH] Login Widget: kalit — bot tokenining SHA-256 xeshi
    secret_key = hashlib.sha256(_widget_token().encode()).digest()
    expected = _hmac_hex(secret_key, _data_check_string(fields))

    if not constant_time_equal(expected, received):
        raise Unauthorized("Widget imzosi mos kelmadi", code="WIDGET_BAD_SIGNATURE")

    auth_date = int(fields.get("auth_date", "0"))
    _check_age(auth_date, settings.widget_ttl_sec)

    if "id" not in fields:
        raise Unauthorized("Widget javobida id yo‘q", code="WIDGET_NO_ID")

    return TelegramIdentity(
        telegram_id=int(fields["id"]),
        first_name=fields.get("first_name", ""),
        last_name=fields.get("last_name"),
        username=fields.get("username"),
        language_code=None,
        photo_url=fields.get("photo_url"),
        auth_date=auth_date,
        raw_hash=received,
        source="widget",
    )
