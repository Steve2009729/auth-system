from pydantic import BaseModel
from datetime import datetime
import uuid


class SessionResponse(BaseModel):
    id: uuid.UUID
    device_info: str | None
    ip_address: str | None
    is_active: bool
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[PermissionResponse]

    class Config:
        from_attributes = True


class UserPermissionsResponse(BaseModel):
    permissions: list[str]  # List of permission names like "users:read", "admin:all"
