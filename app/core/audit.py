import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from app.models.audit_log import AuditLog


async def log_audit_event(
    session: AsyncSession,
    event: str,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None
) -> None:
    """Log an audit event to the database."""
    audit_log = AuditLog(
        user_id=user_id,
        event=event,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
        created_at=datetime.utcnow()
    )
    session.add(audit_log)
    await session.flush()
