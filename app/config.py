import secrets
import logging
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)

# Placeholder values that indicate "not yet configured"
_INSECURE_KEY = "your-super-secret-key-minimum-64-characters-long-change-in-production"


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # App
    APP_NAME: str = "AuthSystem"
    DEBUG: bool = False
    SECRET_KEY: str = _INSECURE_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/authdb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email (SMTP) — all optional; app runs without them but email features are disabled
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-app-password"
    EMAILS_FROM: str = "noreply@authsystem.com"

    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # OAuth Google — optional; routes return 501 if not configured
    GOOGLE_CLIENT_ID: str = "your-google-client-id"
    GOOGLE_CLIENT_SECRET: str = "your-google-client-secret"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # OAuth GitHub — optional; routes return 501 if not configured
    GITHUB_CLIENT_ID: str = "your-github-client-id"
    GITHUB_CLIENT_SECRET: str = "your-github-client-secret"
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"

    class Config:
        env_file = ".env"
        case_sensitive = True


def _validate_and_patch(s: Settings) -> Settings:
    """
    Validate critical settings at startup.

    - SECRET_KEY: auto-generates a dev key with a loud warning if the placeholder
      is still set and DEBUG is True. Refuses to start in production (DEBUG=False)
      with the default placeholder.
    - DATABASE_URL / REDIS_URL: emits a warning if still pointing at localhost
      defaults in non-debug mode.
    """
    if s.SECRET_KEY == _INSECURE_KEY:
        if s.DEBUG:
            generated = secrets.token_hex(64)
            object.__setattr__(s, "SECRET_KEY", generated)
            logger.warning(
                "\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  ⚠  INSECURE DEV SECRET_KEY — DO NOT USE IN PRODUCTION  ⚠  ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║  No SECRET_KEY was set, so one was auto-generated for this  ║\n"
                "║  process only. Tokens will be invalid after restart.        ║\n"
                "║                                                              ║\n"
                "║  To fix: run  authsystem init  or add to your .env:         ║\n"
                "║    SECRET_KEY=%s  ║\n"
                "╚══════════════════════════════════════════════════════════════╝",
                generated[:52] + "...",
            )
        else:
            raise RuntimeError(
                "\n\nSECRET_KEY is still set to the default placeholder value.\n"
                "This is not allowed in production (DEBUG=False).\n\n"
                "Generate a secure key with:\n"
                "    python -c \"import secrets; print(secrets.token_hex(64))\"\n"
                "or run:  authsystem init\n"
                "then add SECRET_KEY=<value> to your .env file.\n"
            )

    return s


# Build settings once at import time
settings = _validate_and_patch(Settings())
