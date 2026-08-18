"""Xodim o'z Telegram'ini bog'laydi — bron bildirishnomasi shu kanal bilan yetadi.

`botlogin.py` bilan bir xil nonce+webhook+poll naqshi (Redis, bir martalik,
TTL'li), lekin natija sessiya EMAS — `staff_telegram` yozuvi
(`0010_staff_telegram_link.py`dagi `staff_telegram_link_confirm()` orqali,
chunki yozish RLS ostida qoladi — GUC'siz SECURITY DEFINER yordam bermaydi,
`[[render-free-tier-no-bypassrls]]`).

Bitta bot, bitta webhook — nonce prefiksi (`lnk_`) ikki oqimni ajratadi
(`auth/router.py`dagi `admin_bot_webhook`).
"""

import json
import logging
import secrets
from typing import Any

from playbron.core.redis import redis_client

log = logging.getLogger("playbron.stafflink")

PREFIX = "lnk_"
_KEY_PREFIX = "auth:tglink:"
START_TTL_SEC = 300
APPROVED_TTL_SEC = 120


def _key(nonce: str) -> str:
    return f"{_KEY_PREFIX}{nonce}"


async def start_link(user_id: int) -> str:
    """Kirgan xodim uchun yangi bog'lash urinishi."""
    nonce = PREFIX + secrets.token_urlsafe(32)
    await redis_client().set(
        _key(nonce),
        json.dumps({"status": "pending", "user_id": user_id}),
        ex=START_TTL_SEC,
    )
    return nonce


async def peek_link(nonce: str) -> int | None:
    """Nonce haqiqiyligini tekshiradi va `user_id` qaytaradi — HOLATGA TEGMAYDI.

    Ilgari bu funksiya `approve_link()` deb atalardi va nonce'ni DARHOL
    "approved" qilib qo'yardi. Konsol polli aynan shu Redis holatini
    o'qiydi, DB yozuvi esa keyin bajarilardi — ya'ni yozuv YIQILSA ham
    konsol "Ulandi" deb ko'rsatardi (loyiha egasi, 2026-08-17: "bot
    1 marta ulandi, log outdan keyin uzildi").

    Endi tartib teskari: peek → DB yozuvi → tekshiruv → `mark_ready()`.
    Konsoldagi "Ulandi" faqat baza yozuvi HAQIQATAN turganini bildiradi.
    """
    raw = await redis_client().get(_key(nonce))
    if raw is None:
        return None

    data: dict[str, Any] = json.loads(raw)
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return None
    return user_id


async def mark_ready(nonce: str, user_id: int) -> None:
    """DB yozuvi tasdiqlangandan KEYIN chaqiriladi — konsol polli shuni ko'radi."""
    await redis_client().set(
        _key(nonce),
        json.dumps({"status": "approved", "user_id": user_id}),
        ex=APPROVED_TTL_SEC,
    )


async def fail_link(nonce: str) -> None:
    """Yozuv yiqildi — nonce o'chiriladi, konsol `expired` oladi.

    Kalit qoldirilsa konsol `pending` bilan aylanaverardi va foydalanuvchi
    sababni bilmasdi; "ready" esa umuman yolg'on bo'lardi.
    """
    await redis_client().delete(_key(nonce))


async def poll_link(nonce: str) -> str:
    """`pending` / `expired` / `ready`. `ready`da kalit bir martalik o'chiriladi."""
    key = _key(nonce)
    raw = await redis_client().get(key)
    if raw is None:
        return "expired"

    data: dict[str, Any] = json.loads(raw)
    if data.get("status") != "approved":
        return "pending"

    deleted = await redis_client().delete(key)
    return "ready" if deleted else "expired"
