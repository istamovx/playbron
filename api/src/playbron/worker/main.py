"""arq worker kirish nuqtasi.

Ishga tushirish (docker-compose `worker` servisi shuni chaqiradi):

    arq playbron.worker.main.WorkerSettings

Vazifalar ro'yxati B2-B3 bosqichlarida to'ladi; skelet `ping` bilan ham
ko'tariladi — konteyner sog'lig'ini tekshirish uchun.
"""

import logging
from typing import Any

from arq.connections import RedisSettings

from playbron.core.config import settings

log = logging.getLogger("playbron.worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Tiriklik tekshiruvi — navbat orqali chaqirib ko'rish mumkin."""
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    log.info("PlayBron worker ishga tushdi (env=%s)", settings.env)


async def shutdown(ctx: dict[str, Any]) -> None:
    from playbron.core import db, redis

    await db.dispose()
    await redis.close()


class WorkerSettings:
    """arq konfiguratsiyasi — vazifalar va cron jadval shu yerda ro'yxatlanadi."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions: "list[Any]" = [ping]
    cron_jobs: "list[Any]" = []
    on_startup = startup
    on_shutdown = shutdown
    # Vazifa yiqilsa arq qayta uradi; jurnal (`jobs.attempts`) buni alohida yozadi
    max_tries = 3
