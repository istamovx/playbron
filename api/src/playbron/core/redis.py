"""Redis — replay himoyasi, kesh va navbat uchun."""

from functools import lru_cache

from redis.asyncio import Redis

from playbron.core.config import settings


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def ping() -> bool:
    return bool(await redis_client().ping())


async def close() -> None:
    await redis_client().aclose()
