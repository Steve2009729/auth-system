from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.base import get_db
from app.db.redis import get_redis
from app.dependencies import get_current_user
from app.schemas.token import SessionResponse
from app.services.session_service import SessionService
from app.models.user import User

router = APIRouter()


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """List all active sessions for current user."""
    session_service = SessionService(session)
    sessions = await session_service.get_user_sessions(current_user.id)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Revoke a specific session."""
    session_service = SessionService(session)
    await session_service.revoke_session(session_id, current_user.id)
    await session.commit()
    return None
