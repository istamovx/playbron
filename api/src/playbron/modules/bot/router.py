"""Telegram webhook'lari.

Manba: `docs/05-auth-redesign.md` §4.4, §5.4.
"""

import hashlib
import hmac
import logging
from typing import Annotated, Any, Final

from fastapi import APIRouter, Header, Request

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.core.security import constant_time_equal
from playbron.modules.bot import customer

log = logging.getLogger("playbron.bot")

router = APIRouter(prefix="/telegram", tags=["telegram"])

SURFACE_CUSTOMER: Final = "customer"
# Admin bot hozircha `botlogin.webhook_secret_token()` dagi o'z sxemasidan
# foydalanadi (u bilan birga o'chiriladi). Ikkala qiymat baribir har xil,
# ya'ni bittasi sizib chiqsa ikkinchisiga soxta update yuborib bo'lmaydi.


def webhook_secret(surface: str) -> str:
    """Har bot uchun ALOHIDA sekret — bitta ildizdan domen ajratish bilan.

    Ikkala webhook bir xil qiymat ishlatsa, bittasi sizib chiqqanda (masalan
    proksi log'ida) hujumchi ikkinchisiga ham soxta update yubora oladi.
    HMAC bilan ajratilganda bir qiymatdan ikkinchisini hosil qilib bo'lmaydi.

    Telegram `secret_token` da faqat `A-Za-z0-9_-` ga ruxsat beradi — hex
    har doim shu to'plamda.
    """
    root = settings.tg_webhook_secret.get_secret_value().encode()
    return hmac.new(root, surface.encode(), hashlib.sha256).hexdigest()


def _authorized(surface: str, presented: str | None) -> bool:
    if not settings.tg_webhook_secret.get_secret_value():
        return False
    if not presented:
        return False
    return constant_time_equal(presented, webhook_secret(surface))


async def register_customer_webhook(public_url: str) -> None:
    """Mijoz botining webhook'ini ro'yxatdan o'tkazadi — API start'ida.

    Bepul rejada Shell yo'q, shuning uchun `setWebhook` qo'lda emas. Idempotent:
    Telegram bir xil URL'ni qayta qabul qilaveradi. Xato start'ni to'xtatmaydi.
    """
    token = settings.bot_token.get_secret_value()
    if not (token and settings.tg_webhook_secret.get_secret_value() and public_url):
        log.warning("Mijoz webhook'i ro'yxatdan o'tkazilmadi — token/sekret/URL to'liq emas")
        return

    url = public_url.rstrip("/") + "/api/v1/telegram/webhook/main"
    result = await telegram_api.call(
        token,
        "setWebhook",
        {
            "url": url,
            "secret_token": webhook_secret(SURFACE_CUSTOMER),
            # Faqat xabarlar kerak: `/start`, ism va kontakt shu turda keladi
            "allowed_updates": ["message"],
        },
    )
    if result is not None:
        log.info("Mijoz bot webhook: %s", url)


@router.post("/webhook/main")
async def customer_webhook(
    request: Request,
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, bool]:
    """Mijoz boti.

    HAR DOIM 200 qaytaradi. Aks holda bitta noto'g'ri update Telegram
    navbatini to'xtatadi va butun ro'yxatdan o'tish oqimi o'ladi.
    Sekret mos kelmasa ham 200 — lekin hech narsa bajarilmaydi.
    """
    if not _authorized(SURFACE_CUSTOMER, secret):
        log.warning("Mijoz webhook'i: sekret mos kelmadi")
        return {"ok": True}

    try:
        update: Any = await request.json()
    except ValueError:
        return {"ok": True}

    if isinstance(update, dict):
        await customer.handle_update(update)

    return {"ok": True}
