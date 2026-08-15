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


async def approve_link(nonce: str) -> int | None:
    """Webhook'dan chaqiriladi — nonce haqiqiyligini tekshiradi.

    Muvaffaqiyatda `user_id` qaytadi (DB yozuvi CHAQIRUVCHIDA amalga oshadi —
    bu modul DB bilan ishlamaydi). Begona/eskirgan nonce — `None`.
    """
    key = _key(nonce)
    current = await redis_client().get(key)
    if current is None:
        return None

    data: dict[str, Any] = json.loads(current)
    user_id = data.get("user_id")
    if not isinstance(user_id, int):
        return None

    await redis_client().set(
        key, json.dumps({"status": "approved", "user_id": user_id}), ex=APPROVED_TTL_SEC
    )
    return user_id


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
