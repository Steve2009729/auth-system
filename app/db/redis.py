from redis.asyncio import Redis
from app.config import settings

redis_pool: Redis | None = None


async def get_redis() -> Redis:
    """Get or create Redis connection pool."""
    global redis_pool
    if redis_pool is None:
        redis_pool = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_pool


async def close_redis():
    """Close Redis connection pool."""
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None
