from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # App
    APP_NAME: str = "AuthSystem"
    DEBUG: bool = False
    SECRET_KEY: str = "your-super-secret-key-minimum-64-characters-long-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/authdb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-app-password"
    EMAILS_FROM: str = "noreply@authsystem.com"

    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # OAuth Google
    GOOGLE_CLIENT_ID: str = "your-google-client-id"
    GOOGLE_CLIENT_SECRET: str = "your-google-client-secret"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # OAuth GitHub
    GITHUB_CLIENT_ID: str = "your-github-client-id"
    GITHUB_CLIENT_SECRET: str = "your-github-client-secret"
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
