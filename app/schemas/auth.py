from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False
    totp_session_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class TwoFASetupResponse(BaseModel):
    secret: str
    qr_code: str
    provisioning_uri: str


class TwoFAVerifyRequest(BaseModel):
    code: str
    session_token: Optional[str] = None


class TOTPEnableRequest(BaseModel):
    code: str


class TOTPDisableRequest(BaseModel):
    password: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
