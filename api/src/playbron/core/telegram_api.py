"""Telegram Bot API — yupqa mijoz.

`[TEKSHIRISH]` metod nomlari va maydonlar rasmiy hujjatdan tasdiqlanishi
kerak: `sendMessage`, `ReplyKeyboardMarkup`, `KeyboardButton.request_contact`,
`ReplyKeyboardRemove`, `setChatMenuButton`, `WebAppInfo`.
"""

import logging
from typing import Any, Final

import httpx

log = logging.getLogger("playbron.telegram")

API: Final = "https://api.telegram.org"
TIMEOUT: Final = 10.0


async def call(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Bot API chaqiruvi. Xato oqimni TO'XTATMAYDI — `None` qaytaradi.

    Sabab: webhook ishlovchisi Telegram'ga har doim 200 qaytarishi kerak.
    Yuborilmagan xabar uchun butun ro'yxatdan o'tish oqimini o'ldirib
    bo'lmaydi.
    """
    if not token:
        log.warning("Bot token sozlanmagan — %s yuborilmadi", method)
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"{API}/bot{token}/{method}", json=payload)
            body: dict[str, Any] = response.json()
            if not body.get("ok"):
                # Token URL ichida — uni log'ga chiqarmaymiz, faqat javobni
                log.warning("%s rad etildi: %s", method, body.get("description"))
                return None
            result = body.get("result")
            return result if isinstance(result, dict) else {}
    except (httpx.HTTPError, ValueError):
        log.warning("%s amalga oshmadi", method, exc_info=True)
        return None


async def send_message(
    token: str,
    chat_id: int,
    text: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    await call(token, "sendMessage", payload)


def contact_keyboard(label: str) -> dict[str, Any]:
    """`request_contact` tugmasi.

    Qo'lda yozilgan raqam QABUL QILINMAYDI — tasdiqning butun ma'nosi shunda.
    """
    return {
        "keyboard": [[{"text": label, "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def remove_keyboard() -> dict[str, Any]:
    return {"remove_keyboard": True}


def name_keyboard(confirm: str, change: str) -> dict[str, Any]:
    """«Ismingiz Xurshidmi?» — bir bosishda tasdiq.

    Telegram ismni allaqachon beradi, shuning uchun 90% holatda foydalanuvchi
    harf yozmaydi.
    """
    return {
        "keyboard": [[{"text": confirm}], [{"text": change}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def webapp_keyboard(label: str, url: str) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": label, "web_app": {"url": url}}]]}
