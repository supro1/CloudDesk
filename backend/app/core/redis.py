from __future__ import annotations

from fakeredis.aioredis import FakeRedis
from redis.asyncio import Redis

from backend.app.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    if settings.use_fake_redis:
        return FakeRedis()
    if settings.redis_url is None:
        raise ValueError("REDIS_URL must be set when USE_FAKE_REDIS is false")
    return Redis.from_url(settings.redis_url)
