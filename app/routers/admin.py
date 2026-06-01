from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.base import get_db
from app.dependencies import get_current_user, require_permission
from app.schemas.user import UserListResponse
from app.services.user_service import UserService
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("/users", response_model=list[UserListResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """List all users (paginated). Requires admin:read permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:read")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:read' required"
        )

    result = await session.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [UserListResponse.from_orm(u) for u in users]


@router.get("/users/{user_id}", response_model=UserListResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Get user by ID. Requires admin:read permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:read")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:read' required"
        )

    user = await user_service.get_user_by_id(user_id)
    return UserListResponse.from_orm(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Update user (lock, unlock, verify). Requires admin:write permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:write")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:write' required"
        )

    user = await user_service.get_user_by_id(user_id)

    # Allow updating specific fields
    allowed_fields = ["is_active", "is_verified", "is_superuser"]
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])

    await session.flush()

    from app.core.audit import log_audit_event
    await log_audit_event(
        session, "admin_user_updated",
        user_id=current_user.id,
        metadata={"target_user_id": str(user_id), "changes": data}
    )

    await session.commit()
    return {"detail": "User updated successfully"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Delete user. Requires admin:delete permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:delete")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:delete' required"
        )

    user = await user_service.get_user_by_id(user_id)
    await session.delete(user)

    from app.core.audit import log_audit_event
    await log_audit_event(
        session, "admin_user_deleted",
        user_id=current_user.id,
        metadata={"deleted_user_id": str(user_id)}
    )

    await session.commit()
    return None


@router.post("/roles")
async def create_role(
    data: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Create new role. Requires admin:all permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:all")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:all' required"
        )

    from app.models.role import Role

    # Check if role already exists
    result = await session.execute(
        select(Role).where(Role.name == data.get("name"))
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already exists"
        )

    role = Role(
        name=data.get("name"),
        description=data.get("description")
    )
    session.add(role)

    from app.core.audit import log_audit_event
    await log_audit_event(
        session, "role_created",
        user_id=current_user.id,
        metadata={"role_name": data.get("name")}
    )

    await session.commit()
    return {"id": str(role.id), "name": role.name}


@router.post("/roles/{role_id}/permissions")
async def assign_permission_to_role(
    role_id: uuid.UUID,
    data: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Assign permissions to role. Requires admin:all permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:all")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:all' required"
        )

    from app.models.role import Role, Permission

    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar()

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    permission_name = data.get("permission_name")
    result = await session.execute(
        select(Permission).where(Permission.name == permission_name)
    )
    permission = result.scalar()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    role.permissions.append(permission)

    from app.core.audit import log_audit_event
    await log_audit_event(
        session, "permission_granted",
        user_id=current_user.id,
        metadata={"role_id": str(role_id), "permission": permission_name}
    )

    await session.commit()
    return {"detail": "Permission assigned"}


@router.post("/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: uuid.UUID,
    data: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Assign role to user. Requires admin:all permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:all")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:all' required"
        )

    from app.models.role import Role, UserRole

    user = await user_service.get_user_by_id(user_id)

    role_id = uuid.UUID(data.get("role_id"))
    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar()

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)

    from app.core.audit import log_audit_event
    await log_audit_event(
        session, "role_assigned",
        user_id=current_user.id,
        metadata={"target_user_id": str(user_id), "role_id": str(role_id)}
    )

    await session.commit()
    return {"detail": "Role assigned"}


@router.get("/audit-logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """View audit logs (filterable). Requires admin:read permission."""
    user_service = UserService(session)
    has_permission = await user_service.check_permission(current_user.id, "admin:read")

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:read' required"
        )

    result = await session.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "event": log.event,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
            "metadata": log.metadata
        }
        for log in logs
    ]
