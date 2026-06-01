import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.user import User
from app.core.audit import log_audit_event
from app.core.security import verify_password


class UserService:
    """User management business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """Get user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar()

    async def update_user(self, user_id: uuid.UUID, **kwargs) -> User:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)

        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)

        await self.session.flush()

        await log_audit_event(
            self.session, "user_profile_updated", user_id=user.id
        )

        return user

    async def delete_user(self, user_id: uuid.UUID, password: str | None = None) -> None:
        """Delete user account."""
        user = await self.get_user_by_id(user_id)

        # If user has a password, require verification
        if user.hashed_password and password:
            if not verify_password(password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password is incorrect"
                )

        await self.session.delete(user)
        await self.session.flush()

        await log_audit_event(
            self.session, "account_deleted", user_id=user.id
        )

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        """Get all permissions for a user."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        permissions = []
        for user_role in user.roles:
            for permission in user_role.role.permissions:
                permissions.append(permission.name)

        return list(set(permissions))  # Remove duplicates

    async def check_permission(self, user_id: uuid.UUID, required_permission: str) -> bool:
        """Check if user has a specific permission."""
        permissions = await self.get_user_permissions(user_id)
        return required_permission in permissions
