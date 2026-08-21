import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from fastapi import HTTPException, status

from app.models.user import User
from app.models.session import Session
from app.models.token import Token, TokenType
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, verify_access_token, generate_secure_token, hash_token
)
from app.core.email import send_verification_email, send_password_reset_email
from app.core.totp import generate_totp_secret, verify_totp, get_totp_uri, generate_qr_code_base64
from app.core.audit import log_audit_event
from app.config import settings


class AuthService:
    """Core authentication business logic."""

    def __init__(self, session: AsyncSession, redis_client=None):
        self.session = session
        self.redis = redis_client

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> tuple[User, str]:
        """Register a new user. Returns (user, verification_token)."""
        # Check if user already exists
        existing = await self.session.execute(
            select(User).where((User.email == email) | (User.username == username))
        )
        if existing.scalar():
            await log_audit_event(
                self.session, "register_failed", ip_address=ip_address,
                extra_data={"reason": "email_or_username_exists"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or username already registered"
            )

        # Create user
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_verified=False
        )
        self.session.add(user)
        await self.session.flush()

        # Generate verification token
        raw_token, hashed_token = generate_secure_token()
        token = Token(
            user_id=user.id,
            token_hash=hashed_token,
            token_type=TokenType.EMAIL_VERIFICATION,
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.session.add(token)
        await self.session.flush()

        await log_audit_event(
            self.session, "register_success",
            user_id=user.id, ip_address=ip_address, user_agent=user_agent
        )

        return user, raw_token

    async def login_user(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_info: str | None = None
    ) -> tuple[str, str, bool, str | None]:
        """
        Login user. Returns (access_token, refresh_token, requires_2fa, totp_session_token).
        """
        # Find user
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar()

        if not user or not user.hashed_password:
            await log_audit_event(
                self.session, "login_failed",
                ip_address=ip_address, user_agent=user_agent,
                extra_data={"reason": "invalid_credentials"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            await log_audit_event(
                self.session, "login_blocked",
                user_id=user.id, ip_address=ip_address,
                extra_data={"reason": "account_locked"}
            )
            remaining = (user.locked_until - datetime.utcnow()).total_seconds()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {int(remaining)} seconds"
            )

        # Verify password
        if not verify_password(password, user.hashed_password):
            # Increment failed attempts
            user.failed_login_attempts += 1

            # Lock account based on attempts
            if user.failed_login_attempts >= 10:
                user.locked_until = datetime.utcnow() + timedelta(hours=24)
            elif user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            elif user.failed_login_attempts >= 3:
                user.locked_until = datetime.utcnow() + timedelta(minutes=5)

            await self.session.flush()

            await log_audit_event(
                self.session, "login_failed",
                user_id=user.id, ip_address=ip_address,
                extra_data={"reason": "invalid_password", "attempts": user.failed_login_attempts}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Check if user is active
        if not user.is_active:
            await log_audit_event(
                self.session, "login_failed",
                user_id=user.id, ip_address=ip_address,
                extra_data={"reason": "account_inactive"}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Check if 2FA is enabled
        if user.totp_enabled:
            # Generate temporary session token for 2FA verification
            totp_session_token = secrets.token_urlsafe(32)
            if self.redis:
                await self.redis.setex(
                    f"totp_session:{totp_session_token}",
                    300,  # 5 minutes
                    str(user.id)
                )

            await log_audit_event(
                self.session, "login_requires_2fa",
                user_id=user.id, ip_address=ip_address
            )

            return "", "", True, totp_session_token

        # Success: reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        user.last_login_ip = ip_address
        await self.session.flush()

        # Create tokens
        access_token = create_access_token(str(user.id), {"email": user.email})
        refresh_token_raw, refresh_token_hash = create_refresh_token()

        # Create session
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = Session(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=expires_at
        )
        self.session.add(session)
        await self.session.flush()

        await log_audit_event(
            self.session, "login_success",
            user_id=user.id, ip_address=ip_address, user_agent=user_agent
        )

        return access_token, refresh_token_raw, False, None

    async def verify_email(self, token: str) -> User:
        """Verify email with token."""
        token_hash = hash_token(token)

        result = await self.session.execute(
            select(Token).where(
                and_(
                    Token.token_hash == token_hash,
                    Token.token_type == TokenType.EMAIL_VERIFICATION,
                    Token.is_used == False,
                    Token.expires_at > datetime.utcnow()
                )
            )
        )
        token_obj = result.scalar()

        if not token_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )

        # Mark token as used
        token_obj.is_used = True

        # Mark user as verified
        result = await self.session.execute(select(User).where(User.id == token_obj.user_id))
        user = result.scalar()
        user.is_verified = True
        await self.session.flush()

        await log_audit_event(
            self.session, "email_verified", user_id=user.id
        )

        return user

    async def request_password_reset(self, email: str, ip_address: str | None = None) -> str:
        """Request password reset. Returns token."""
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar()

        if not user:
            # Don't reveal if user exists
            return ""

        # Generate reset token
        raw_token, hashed_token = generate_secure_token()
        token = Token(
            user_id=user.id,
            token_hash=hashed_token,
            token_type=TokenType.PASSWORD_RESET,
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.session.add(token)
        await self.session.flush()

        await log_audit_event(
            self.session, "password_reset_requested",
            user_id=user.id, ip_address=ip_address
        )

        return raw_token

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset password with token."""
        token_hash = hash_token(token)

        result = await self.session.execute(
            select(Token).where(
                and_(
                    Token.token_hash == token_hash,
                    Token.token_type == TokenType.PASSWORD_RESET,
                    Token.is_used == False,
                    Token.expires_at > datetime.utcnow()
                )
            )
        )
        token_obj = result.scalar()

        if not token_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        # Update password
        result = await self.session.execute(select(User).where(User.id == token_obj.user_id))
        user = result.scalar()
        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()

        # Mark token as used
        token_obj.is_used = True

        await self.session.flush()

        await log_audit_event(
            self.session, "password_reset_success", user_id=user.id
        )

        return user

    async def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> User:
        """Change password for authenticated user."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user or not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found or has no password"
            )

        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )

        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()
        await self.session.flush()

        await log_audit_event(
            self.session, "password_changed", user_id=user.id
        )

        return user

    async def setup_2fa(self, user_id: uuid.UUID) -> tuple[str, str, str]:
        """Setup 2FA for user. Returns (secret, qr_code, provisioning_uri)."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        secret = generate_totp_secret()
        uri = get_totp_uri(secret, user.email)
        qr_code = generate_qr_code_base64(uri)

        await log_audit_event(
            self.session, "totp_setup_initiated", user_id=user.id
        )

        return secret, qr_code, uri

    async def enable_2fa(self, user_id: uuid.UUID, secret: str, code: str) -> User:
        """Enable 2FA after verifying the code."""
        if not verify_totp(secret, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code"
            )

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.totp_secret = secret
        user.totp_enabled = True
        await self.session.flush()

        await log_audit_event(
            self.session, "totp_enabled", user_id=user.id
        )

        return user

    async def disable_2fa(self, user_id: uuid.UUID, password: str) -> User:
        """Disable 2FA after verifying password."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user or not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )

        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password is incorrect"
            )

        user.totp_secret = None
        user.totp_enabled = False
        await self.session.flush()

        await log_audit_event(
            self.session, "totp_disabled", user_id=user.id
        )

        return user

    async def verify_2fa(self, session_token: str, code: str, ip_address: str | None = None) -> tuple[str, str]:
        """Verify 2FA code and return tokens."""
        if not self.redis:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis not available"
            )

        user_id_str = await self.redis.get(f"totp_session:{session_token}")

        if not user_id_str:
            await log_audit_event(
                self.session, "totp_failed", ip_address=ip_address,
                extra_data={"reason": "invalid_session"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired 2FA session"
            )

        user_id = uuid.UUID(user_id_str)
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar()

        if not user or not user.totp_enabled or not user.totp_secret:
            await log_audit_event(
                self.session, "totp_failed", user_id=user_id, ip_address=ip_address,
                extra_data={"reason": "2fa_not_enabled"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA not enabled for this account"
            )

        if not verify_totp(user.totp_secret, code):
            await log_audit_event(
                self.session, "totp_failed", user_id=user.id, ip_address=ip_address,
                extra_data={"reason": "invalid_code"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code"
            )

        # Delete the temporary session
        await self.redis.delete(f"totp_session:{session_token}")

        # Create tokens
        access_token = create_access_token(str(user.id), {"email": user.email})
        refresh_token_raw, refresh_token_hash = create_refresh_token()

        # Create session
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = Session(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            ip_address=ip_address,
            is_active=True,
            expires_at=expires_at
        )
        self.session.add(session)
        await self.session.flush()

        await log_audit_event(
            self.session, "login_success", user_id=user.id, ip_address=ip_address
        )

        return access_token, refresh_token_raw
