from redis.asyncio import Redis
from fastapi import HTTPException, status


class RateLimiter:
    """Redis-based sliding window rate limiter."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        """Check rate limit. Raises 429 if exceeded."""
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window_seconds)
        if current > max_requests:
            ttl = await self.redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)}
            )

    async def login_limit(self, ip: str) -> None:
        """5 login attempts per 5 minutes."""
        await self.check(f"rate:login:{ip}", max_requests=5, window_seconds=300)

    async def register_limit(self, ip: str) -> None:
        """3 registrations per hour."""
        await self.check(f"rate:register:{ip}", max_requests=3, window_seconds=3600)

    async def password_reset_limit(self, ip: str) -> None:
        """3 password reset requests per hour."""
        await self.check(f"rate:reset:{ip}", max_requests=3, window_seconds=3600)

    async def refresh_limit(self, ip: str) -> None:
        """10 refresh attempts per minute."""
        await self.check(f"rate:refresh:{ip}", max_requests=10, window_seconds=60)

    async def resend_verification_limit(self, ip: str) -> None:
        """5 resend requests per hour."""
        await self.check(f"rate:resend_email:{ip}", max_requests=5, window_seconds=3600)

    async def blacklist_token(self, jti: str, expire_seconds: int) -> None:
        """Add token to blacklist."""
        await self.redis.setex(f"blacklist:{jti}", expire_seconds, "1")

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted."""
        return await self.redis.exists(f"blacklist:{jti}") == 1
