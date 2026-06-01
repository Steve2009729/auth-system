import uuid
import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from fastapi import HTTPException, status

from app.models.session import Session
from app.models.user import User
from app.core.security import create_refresh_token, hash_token, create_access_token
from app.core.audit import log_audit_event
from app.config import settings
from datetime import timedelta


class SessionService:
    """Session and token management."""

    def __init__(self, session: AsyncSession, redis_client=None):
        self.session = session
        self.redis = redis_client

    async def get_user_sessions(self, user_id: uuid.UUID) -> list[Session]:
        """Get all active sessions for a user."""
        result = await self.session.execute(
            select(Session).where(
                and_(
                    Session.user_id == user_id,
                    Session.is_active == True
                )
            )
        )
        return result.scalars().all()

    async def get_session_by_refresh_token(self, refresh_token_hash: str) -> Session | None:
        """Get session by refresh token hash."""
        result = await self.session.execute(
            select(Session).where(
                and_(
                    Session.refresh_token_hash == refresh_token_hash,
                    Session.is_active == True,
                    Session.expires_at > datetime.utcnow()
                )
            )
        )
        return result.scalar()

    async def refresh_access_token(self, refresh_token: str, ip_address: str | None = None) -> tuple[str, str]:
        """
        Refresh tokens with rotation.
        Returns (new_access_token, new_refresh_token).
        Implements refresh token rotation for security.
        """
        refresh_token_hash = hash_token(refresh_token)
        session = await self.get_session_by_refresh_token(refresh_token_hash)

        if not session:
            # Possible replay attack
            if self.redis:
                await self.redis.setex(f"refresh_replay:{refresh_token_hash}", 3600, "1")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        # Check for replay attack (same token used twice)
        if self.redis:
            is_replayed = await self.redis.exists(f"refresh_replay:{refresh_token_hash}")
            if is_replayed:
                # Revoke all sessions for this user
                await self.revoke_all_sessions(session.user_id)
                await log_audit_event(
                    self.session, "refresh_token_replay_detected",
                    user_id=session.user_id, ip_address=ip_address
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token replay detected. All sessions revoked for security."
                )

        # Get user
        result = await self.session.execute(select(User).where(User.id == session.user_id))
        user = result.scalar()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive"
            )

        # Invalidate old refresh token
        session.is_active = False

        # Create new tokens
        access_token = create_access_token(str(user.id), {"email": user.email})
        new_refresh_token_raw, new_refresh_token_hash = create_refresh_token()

        # Create new session
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        new_session = Session(
            user_id=user.id,
            refresh_token_hash=new_refresh_token_hash,
            device_info=session.device_info,
            ip_address=ip_address,
            user_agent=session.user_agent,
            is_active=True,
            expires_at=expires_at
        )
        self.session.add(new_session)
        session.last_used_at = datetime.utcnow()

        await self.session.flush()

        await log_audit_event(
            self.session, "token_refreshed",
            user_id=user.id, ip_address=ip_address
        )

        return access_token, new_refresh_token_raw

    async def revoke_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Revoke a specific session."""
        result = await self.session.execute(
            select(Session).where(
                and_(
                    Session.id == session_id,
                    Session.user_id == user_id
                )
            )
        )
        session_obj = result.scalar()

        if not session_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        session_obj.is_active = False
        await self.session.flush()

        await log_audit_event(
            self.session, "session_revoked",
            user_id=user_id, metadata={"session_id": str(session_id)}
        )

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        """Revoke all sessions for a user."""
        result = await self.session.execute(
            select(Session).where(Session.user_id == user_id)
        )
        sessions = result.scalars().all()

        for s in sessions:
            s.is_active = False

        await self.session.flush()

        await log_audit_event(
            self.session, "logout_all_sessions", user_id=user_id
        )

    async def blacklist_access_token(self, user_id: uuid.UUID, token: str) -> None:
        """Blacklist an access token on logout."""
        if self.redis:
            # Create a unique identifier for the token (JTI)
            jti = hashlib.sha256(f"{user_id}:{token}".encode()).hexdigest()
            # Blacklist for the duration of the token's validity
            await self.redis.setex(f"blacklist:{jti}", settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, "1")
