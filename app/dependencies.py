import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.redis import get_redis
from app.core.security import verify_access_token
from app.services.user_service import UserService
from app.models.user import User
from redis.asyncio import Redis

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials

    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No user ID in token")
        user_id = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserService(session)
    user = await user_service.get_user_by_id(user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_permission(permission: str):
    """Create a dependency that requires a specific permission."""
    async def check_permission(
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db)
    ) -> User:
        user_service = UserService(session)
        has_permission = await user_service.check_permission(current_user.id, permission)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )

        return current_user

    return check_permission


async def get_redis_client() -> Redis:
    """Get Redis client."""
    return await get_redis()


def get_client_ip(request) -> str:
    """Extract client IP from request."""
    if request.headers.get("x-forwarded-for"):
        return request.headers.get("x-forwarded-for").split(",")[0].strip()
    return request.client.host if request.client else ""
