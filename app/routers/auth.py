from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlencode

from app.db.base import get_db
from app.db.redis import get_redis
from app.dependencies import get_current_user, get_client_ip
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest, TokenResponse,
    RefreshTokenRequest, PasswordResetRequest, PasswordResetConfirm,
    PasswordChangeRequest, TwoFASetupResponse, TwoFAVerifyRequest,
    TOTPEnableRequest, TOTPDisableRequest, ResendVerificationRequest
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.core.rate_limiter import RateLimiter
from app.core.email import send_verification_email, send_password_reset_email
from app.core.oauth2 import google_oauth, github_oauth, google_enabled, github_enabled
from app.models.user import User
from app.config import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Register a new user with email and password."""
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    # Rate limit
    rate_limiter = RateLimiter(redis)
    await rate_limiter.register_limit(ip)

    auth_service = AuthService(session, redis)
    user, verification_token = await auth_service.register_user(
        email=data.email,
        username=data.username,
        password=data.password,
        full_name=data.full_name,
        ip_address=ip,
        user_agent=user_agent
    )

    # Send verification email
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    await send_verification_email(user.email, verification_link)

    await session.commit()
    return UserResponse.from_orm(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Login with email and password."""
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    # Rate limit
    rate_limiter = RateLimiter(redis)
    await rate_limiter.login_limit(ip)

    auth_service = AuthService(session, redis)
    access_token, refresh_token, requires_2fa, totp_session_token = await auth_service.login_user(
        email=data.email,
        password=data.password,
        ip_address=ip,
        user_agent=user_agent,
        device_info=request.headers.get("user-agent", "Unknown")
    )

    await session.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_2fa=requires_2fa,
        totp_session_token=totp_session_token
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Logout and blacklist access token."""
    session_service = SessionService(session)
    # Revoke first active session (the one used for this request)
    sessions = await session_service.get_user_sessions(current_user.id)
    if sessions:
        await session_service.revoke_session(sessions[0].id, current_user.id)

    await session.commit()
    return None


@router.post("/logout/all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Logout from all devices."""
    session_service = SessionService(session)
    await session_service.revoke_all_sessions(current_user.id)
    await session.commit()
    return None


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Refresh access token using refresh token."""
    ip = get_client_ip(request)

    # Rate limit
    rate_limiter = RateLimiter(redis)
    await rate_limiter.refresh_limit(ip)

    session_service = SessionService(session, redis)
    access_token, new_refresh_token = await session_service.refresh_access_token(
        data.refresh_token,
        ip_address=ip
    )

    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.get("/verify-email/{token}", response_model=UserResponse)
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_db)
):
    """Verify email with token from email link."""
    auth_service = AuthService(session)
    user = await auth_service.verify_email(token)
    await session.commit()
    return UserResponse.from_orm(user)


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    data: ResendVerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis)
):
    """Resend email verification. Always returns 200 to avoid user enumeration."""
    from sqlalchemy import select as _select
    from app.core.security import generate_secure_token
    from app.models.token import Token, TokenType
    from datetime import datetime, timedelta

    ip = get_client_ip(request)
    rate_limiter = RateLimiter(redis)
    await rate_limiter.resend_verification_limit(ip)

    # Look up user — same response whether they exist or not
    result = await session.execute(_select(User).where(User.email == data.email))
    user = result.scalar()

    if user and not user.is_verified:
        raw_token, hashed_token = generate_secure_token()
        token = Token(
            user_id=user.id,
            token_hash=hashed_token,
            token_type=TokenType.EMAIL_VERIFICATION,
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        session.add(token)
        await session.flush()

        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
        await send_verification_email(data.email, verification_link)

    await session.commit()
    return {"detail": "Verification email sent if account exists and is unverified"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    data: PasswordResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Request password reset."""
    ip = get_client_ip(request)

    rate_limiter = RateLimiter(redis)
    await rate_limiter.password_reset_limit(ip)

    auth_service = AuthService(session, redis)
    token = await auth_service.request_password_reset(data.email, ip_address=ip)

    if token:
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        await send_password_reset_email(data.email, reset_link)

    await session.commit()

    return {"detail": "Password reset email sent if account exists"}


@router.post("/reset-password", response_model=UserResponse)
async def reset_password(
    data: PasswordResetConfirm,
    session: AsyncSession = Depends(get_db)
):
    """Reset password with token."""
    auth_service = AuthService(session)
    user = await auth_service.reset_password(data.token, data.new_password)
    await session.commit()
    return UserResponse.from_orm(user)


@router.post("/change-password", response_model=UserResponse)
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Change password for authenticated user."""
    auth_service = AuthService(session)
    user = await auth_service.change_password(
        current_user.id,
        data.current_password,
        data.new_password
    )
    await session.commit()
    return UserResponse.from_orm(user)


@router.get("/google")
async def google_login(request: Request):
    """Redirect to Google OAuth."""
    if not google_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server."
        )
    uri, state = google_oauth.get_authorization_url()
    return {"authorization_url": uri}


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Handle Google OAuth callback."""
    if not google_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server."
        )
    from sqlalchemy import select
    from app.models.user import User

    token = await google_oauth.get_access_token(code, state)
    user_info = await google_oauth.get_user_info(token)

    # Find or create user
    result = await session.execute(
        select(User).where(User.oauth_id == user_info.get("sub"))
    )
    user = result.scalar()

    if not user:
        user = User(
            email=user_info.get("email"),
            username=user_info.get("email").split("@")[0],
            full_name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
            oauth_provider="google",
            oauth_id=user_info.get("sub"),
            is_verified=True
        )
        session.add(user)
        await session.flush()

    # Create tokens
    auth_service = AuthService(session, redis)
    from app.core.security import create_access_token, create_refresh_token
    from app.models.session import Session
    from datetime import datetime, timedelta

    access_token = create_access_token(str(user.id), {"email": user.email})
    refresh_token_raw, refresh_token_hash = create_refresh_token()

    expires_at = datetime.utcnow() + timedelta(days=7)
    session_obj = Session(
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        ip_address="",
        is_active=True,
        expires_at=expires_at
    )
    session.add(session_obj)

    from app.core.audit import log_audit_event
    await log_audit_event(session, "oauth_login_google", user_id=user.id)

    await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_raw,
        "token_type": "bearer"
    }


@router.get("/github")
async def github_login():
    """Redirect to GitHub OAuth."""
    if not github_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured on this server."
        )
    uri, state = github_oauth.get_authorization_url()
    return {"authorization_url": uri}


@router.get("/github/callback")
async def github_callback(
    code: str,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Handle GitHub OAuth callback."""
    if not github_enabled():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured on this server."
        )
    from sqlalchemy import select
    from app.models.user import User

    token = await github_oauth.get_access_token(code)
    user_info = await github_oauth.get_user_info(token)

    # Find or create user
    result = await session.execute(
        select(User).where(User.oauth_id == str(user_info.get("id")))
    )
    user = result.scalar()

    if not user:
        user = User(
            email=user_info.get("email"),
            username=user_info.get("login"),
            full_name=user_info.get("name"),
            avatar_url=user_info.get("avatar_url"),
            oauth_provider="github",
            oauth_id=str(user_info.get("id")),
            is_verified=True
        )
        session.add(user)
        await session.flush()

    # Create tokens
    from app.core.security import create_access_token, create_refresh_token
    from app.models.session import Session
    from datetime import datetime, timedelta

    access_token = create_access_token(str(user.id), {"email": user.email})
    refresh_token_raw, refresh_token_hash = create_refresh_token()

    expires_at = datetime.utcnow() + timedelta(days=7)
    session_obj = Session(
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        ip_address="",
        is_active=True,
        expires_at=expires_at
    )
    session.add(session_obj)

    from app.core.audit import log_audit_event
    await log_audit_event(session, "oauth_login_github", user_id=user.id)

    await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_raw,
        "token_type": "bearer"
    }


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis)
):
    """
    Setup 2FA — generate a TOTP secret and QR code.

    The secret is temporarily stored in Redis (keyed to the user) for 10 minutes.
    Call POST /2fa/enable with the TOTP code from your authenticator app to confirm
    and permanently enable 2FA.
    """
    auth_service = AuthService(session)
    secret, qr_code, uri = await auth_service.setup_2fa(current_user.id)

    # Store secret in Redis so /2fa/enable can retrieve it without sending it back
    # from the client (which would expose it in a second request).
    await redis.setex(f"totp_pending:{current_user.id}", 600, secret)

    return TwoFASetupResponse(secret=secret, qr_code=qr_code, provisioning_uri=uri)


@router.post("/2fa/enable", response_model=UserResponse)
async def enable_2fa(
    data: TOTPEnableRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis=Depends(get_redis)
):
    """
    Enable 2FA after scanning the QR code.

    Provide the 6-digit code from your authenticator app. The pending secret
    must have been generated within the last 10 minutes via POST /2fa/setup.
    """
    # Retrieve the pending secret from Redis
    secret = await redis.get(f"totp_pending:{current_user.id}")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending 2FA setup found. Call POST /auth/2fa/setup first, "
                   "then enable within 10 minutes."
        )

    auth_service = AuthService(session)
    user = await auth_service.enable_2fa(current_user.id, secret, data.code)

    # Clean up the pending secret
    await redis.delete(f"totp_pending:{current_user.id}")

    await session.commit()
    return UserResponse.from_orm(user)


@router.post("/2fa/disable", response_model=UserResponse)
async def disable_2fa(
    data: TOTPDisableRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Disable 2FA."""
    auth_service = AuthService(session)
    user = await auth_service.disable_2fa(current_user.id, data.password)
    await session.commit()
    return UserResponse.from_orm(user)


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(
    data: TwoFAVerifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Verify 2FA code during login."""
    ip = get_client_ip(request)

    auth_service = AuthService(session, redis)
    access_token, refresh_token = await auth_service.verify_2fa(
        data.session_token,
        data.code,
        ip_address=ip
    )

    await session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
