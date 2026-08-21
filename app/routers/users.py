from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.token import UserPermissionsResponse
from app.services.user_service import UserService
from app.models.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Update user profile (name, avatar)."""
    user_service = UserService(session)
    user = await user_service.update_user(
        current_user.id,
        full_name=data.full_name,
        avatar_url=data.avatar_url
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Delete own account."""
    user_service = UserService(session)
    await user_service.delete_user(current_user.id)
    await session.commit()
    return None


@router.get("/me/permissions", response_model=UserPermissionsResponse)
async def get_permissions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Get current user's permissions."""
    user_service = UserService(session)
    permissions = await user_service.get_user_permissions(current_user.id)
    return UserPermissionsResponse(permissions=permissions)
