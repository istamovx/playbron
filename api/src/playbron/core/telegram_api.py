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


async def get_me(token: str) -> dict[str, Any] | None:
    """Bot profilini oladi — `username`, deep-link (`tg://resolve?domain=`)
    yasash uchun. Frontend tokenni HECH QACHON bilmaydi, faqat shu orqali
    olingan username'ni (loyiha egasining so'rovi, 2026-08-16: "Telegram
    bog'lash" tugmasi)."""
    return await call(token, "getMe", {})


def callback_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    """`rows` — har biri `(matn, callback_data)` juftliklari qatori."""
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for text, data in row] for row in rows
        ]
    }


async def answer_callback_query(
    token: str, callback_query_id: str, text: str | None = None
) -> None:
    """Telegram'ning "yuklanmoqda" soatchasi tugmani bosgandan keyin
    UZOQ osilib qolmasin — har bir callback_query albatta javob olishi
    shart (Bot API talabi)."""
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    await call(token, "answerCallbackQuery", payload)


async def download_file(token: str, file_id: str) -> tuple[bytes, str] | None:
    """To'lov chekini ko'rsatish uchun (reja #37, 2026-08-16): rasm bazada
    saqlanmaydi, faqat Telegram `file_id`. Frontend hech qachon Telegram
    fayl URL'ini to'g'ridan olmaydi — u TOKENNI o'z ichiga oladi
    (`https://api.telegram.org/file/bot<TOKEN>/...`); shuning uchun backend
    proxy qiladi: shu yerda yuklab olib, baytlarni o'zi qaytaradi.

    `(bytes, content_type)` yoki xato/topilmasa `None`.
    """
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            meta = await client.get(f"{API}/bot{token}/getFile", params={"file_id": file_id})
            meta_body: dict[str, Any] = meta.json()
            if not meta_body.get("ok"):
                log.warning("getFile rad etildi: %s", meta_body.get("description"))
                return None
            file_path = meta_body.get("result", {}).get("file_path")
            if not isinstance(file_path, str) or not file_path:
                return None

            resp = await client.get(f"{API}/file/bot{token}/{file_path}")
            if resp.status_code != 200:
                log.warning("Fayl yuklanmadi: %s", resp.status_code)
                return None
            content_type = resp.headers.get("content-type", "application/octet-stream")
            return resp.content, content_type
    except httpx.HTTPError:
        log.warning("download_file amalga oshmadi", exc_info=True)
        return None
