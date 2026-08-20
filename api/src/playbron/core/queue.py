"""API → worker: arq navbatiga vazifa qo'yish (best-effort).

Navbatning yiqilishi asosiy oqimni TO'XTATMAYDI: masalan smena yopilishi
bildirishnoma keta olmagani sababli xato bermasligi kerak — yozuv DB'da,
xabar esa ikkinchi darajali. Muvaffaqiyatsizlik log'ga tushadi.
"""

import logging
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from playbron.core.config import settings

log = logging.getLogger("playbron.queue")

_pool: ArqRedis | None = None


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue(job: str, *args: Any, **kwargs: Any) -> bool:
    """Vazifani navbatga qo'yadi. Muvaffaqiyat — True; xato yutiladi."""
    try:
        pool = await _get_pool()
        await pool.enqueue_job(job, *args, **kwargs)
        return True
    except Exception:  # noqa: BLE001 — navbat best-effort, oqimni to'xtatmaydi
        log.warning("Navbatga qo'yilmadi: %s", job, exc_info=True)
        return False


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
