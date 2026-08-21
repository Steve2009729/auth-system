from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import auth, users, sessions, admin
from app.db.base import engine, Base
from app.db.redis import close_redis
from app.config import settings
import app.models  # force-register all models with Base.metadata

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    yield

    # Shutdown
    logger.info("Closing connections...")
    await close_redis()
    await engine.dispose()
    logger.info("Connections closed")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Authentication & Authorization API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": settings.APP_NAME}


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=settings.DEBUG
    )
