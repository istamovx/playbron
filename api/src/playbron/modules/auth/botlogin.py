"""Bot orqali kirish — deep-link + webhook + poll. OAuth oynasi yo'q.

Oqim:
  1. Konsol `POST /auth/telegram/start` bilan nonce oladi va foydalanuvchini
     `tg://resolve?domain=<bot>&start=<nonce>` ga yo'naltiradi — Telegram
     desktop/mobil ilovasi ochiladi.
  2. Foydalanuvchi botda **Start** bosadi. Telegram webhook'ga update yuboradi,
     nonce tasdiqlanib profil Redis'ga yoziladi.
  3. Konsol nonce'ni poll qiladi; tasdiqlangach profil **bir marta** iste'mol
     qilinadi va oddiy sessiya beriladi (`service.sign_in`).

Ishonch modeli: profil imzo bilan emas, **Telegram'ning o'zi** yuborgan webhook
bilan keladi — webhook esa `X-Telegram-Bot-Api-Secret-Token` sarlavhasi bilan
himoyalangan (`setWebhook` da o'rnatiladi). Nonce — 32 baytli tasodifiy sir,
TTL 5 daqiqa, bir marta ishlaydi; uni bilgan brauzergina sessiyani oladi.

Bu oqim @BotFather'dagi `/setdomain` ni talab qilmaydi.
"""

import hashlib
import json
import logging
import secrets
from typing import Any

import httpx

from playbron.core.config import settings
from playbron.core.redis import redis_client

log = logging.getLogger("playbron.botlogin")


def webhook_secret_token() -> str:
    """`setWebhook` uchun sekret — env qiymatining SHA-256 hex'i.

    Telegram `secret_token` da faqat `A-Za-z0-9_-` ga ruxsat beradi, Render'ning
    `generateValue` yasagan qiymatida esa boshqa belgilar bo'lishi mumkin (aynan
    shu sabab ro'yxat 400 bilan yiqilgan). Hex har doim ruxsat etilgan to'plamda,
    entropiya esa saqlanadi. Kiruvchi webhook ham shu qiymat bilan solishtiriladi.
    """
    return hashlib.sha256(settings.tg_webhook_secret.get_secret_value().encode()).hexdigest()

START_PREFIX = "auth:tgstart:"
# Havola ochilib, Start bosilguncha yetarli muddat
START_TTL_SEC = 300
# Tasdiqdan keyin konsol poll'i olib ketishi uchun qisqa muddat kifoya
APPROVED_TTL_SEC = 120

TELEGRAM_API = "https://api.telegram.org"


def _key(nonce: str) -> str:
    return f"{START_PREFIX}{nonce}"


async def start_login(lang: str = "uz") -> str:
    """Yangi kirish urinishi — nonce yaratib, kutish holatida saqlaydi.

    `lang` — konsolda tanlangan til. Botning javobi Telegram ilovasining
    tiliga emas, aynan shu tanlovga mos bo'ladi.
    """
    nonce = secrets.token_urlsafe(32)
    await redis_client().set(
        _key(nonce),
        json.dumps({"status": "pending", "lang": lang}),
        ex=START_TTL_SEC,
    )
    return nonce


async def approve_login(nonce: str, profile: dict[str, Any]) -> str | None:
    """Webhook'dan kelgan Start'ni tasdiqlaydi.

    Muvaffaqiyatda konsolda tanlangan tilni qaytaradi (bot javobi uchun).
    Begona yoki eskirgan nonce — `None`; Telegram'ga baribir 200 qaytadi.
    """
    key = _key(nonce)
    current = await redis_client().get(key)
    if current is None:
        return None

    data: dict[str, Any] = json.loads(current)
    lang = str(data.get("lang") or "uz")

    await redis_client().set(
        key,
        json.dumps({"status": "approved", "profile": profile, "lang": lang}),
        ex=APPROVED_TTL_SEC,
    )
    return lang


async def poll_login(nonce: str) -> tuple[str, dict[str, Any] | None]:
    """Konsol poll'i: `pending` / `expired` / (`ready`, profil).

    `ready` holatda kalit atomik o'chiriladi — profil ikkinchi marta berilmaydi.
    Parallel ikkita poll kelsa `DELETE` faqat bittasida 1 qaytaradi.
    """
    key = _key(nonce)
    raw = await redis_client().get(key)
    if raw is None:
        return ("expired", None)

    data: dict[str, Any] = json.loads(raw)
    if data.get("status") != "approved":
        return ("pending", None)

    deleted = await redis_client().delete(key)
    if not deleted:
        return ("expired", None)

    profile = data.get("profile")
    return ("ready", profile) if isinstance(profile, dict) else ("expired", None)


def extract_start(update: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Update ichidan `/start <nonce>` va yuboruvchi profilini ajratadi.

    Boshqa har qanday update (oddiy xabar, callback, edit) — None.
    """
    message = update.get("message")
    if not isinstance(message, dict):
        return None

    text = message.get("text")
    sender = message.get("from")
    if not isinstance(text, str) or not isinstance(sender, dict) or "id" not in sender:
        return None

    parts = text.split(maxsplit=1)
    if len(parts) != 2 or parts[0] != "/start":
        return None

    nonce = parts[1].strip()
    return (nonce, sender) if nonce else None


# Bot javoblari foydalanuvchi tilida — konsol i18n'i bilan bir xil uch til
_CONFIRM_TEXT: dict[str, str] = {
    "uz": "✅ Kirish tasdiqlandi — konsol oynasiga qayting.",
    "ru": "✅ Вход подтверждён — вернитесь в окно консоли.",
    "en": "✅ Sign-in confirmed — return to the console tab.",
}
_EXPIRED_TEXT: dict[str, str] = {
    "uz": "⏱ Kirish havolasi eskirgan. Konsolda tugmani qaytadan bosing.",
    "ru": "⏱ Ссылка для входа устарела. Нажмите кнопку в консоли ещё раз.",
    "en": "⏱ The sign-in link has expired. Press the button in the console again.",
}


def _admin_token() -> str:
    """Konsol oqimi admin bot bilan ishlaydi; lokalda asosiy botga qaytadi."""
    return settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()


async def notify(chat_id: int, language_code: str | None, *, approved: bool) -> None:
    """Foydalanuvchiga botda natijani aytadi. Xato oqimni to'xtatmaydi."""
    token = _admin_token()
    if not token:
        return

    texts = _CONFIRM_TEXT if approved else _EXPIRED_TEXT
    lang = (language_code or "uz").split("-")[0].lower()
    text = texts.get(lang, texts["uz"])

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    except httpx.HTTPError:
        log.warning("sendMessage yetib bormadi (chat_id=%s)", chat_id)


async def register_webhook(public_url: str) -> None:
    """Admin bot webhook'ini ro'yxatdan o'tkazadi — API start'ida chaqiriladi.

    Bepul rejada Shell yo'q, shuning uchun `setWebhook` qo'lda emas, shu yerda.
    Idempotent: Telegram bir xil URL'ni qayta qabul qilaveradi. Xato start'ni
    to'xtatmaydi — webhook'siz ham API'ning qolgan qismi ishlayveradi.
    """
    token = _admin_token()
    secret = settings.tg_webhook_secret.get_secret_value()
    if not (token and secret and public_url):
        log.warning("Webhook ro'yxatdan o'tkazilmadi — token/sekret/URL to'liq emas")
        return

    url = public_url.rstrip("/") + "/api/v1/auth/telegram/webhook/admin"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TELEGRAM_API}/bot{token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": webhook_secret_token(),
                    # Faqat xabarlar kerak — /start shu turda keladi.
                    # Uxlab qolgan xizmat uyg'onganda navbatdagi update'lar
                    # yetkaziladi, shuning uchun pending'lar tashlanmaydi.
                    "allowed_updates": ["message"],
                },
            )
            body = resp.json()
            if body.get("ok"):
                log.info("Admin bot webhook: %s", url)
            else:
                log.warning("setWebhook rad etildi: %s", body)
    except httpx.HTTPError:
        log.warning("setWebhook amalga oshmadi", exc_info=True)
