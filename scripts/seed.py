"""
Seed script — creates default roles, permissions, an admin user, and a demo user.

Usage:
    python scripts/seed.py

Environment:
    Reads DATABASE_URL from .env (or environment).
    Skips any object that already exists, so it's safe to run multiple times.
"""
import asyncio
import os
import sys

# Allow running from the project root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.role import Role, Permission, UserRole
from app.core.security import hash_password

# ── Default seed data ─────────────────────────────────────────────────────────

DEFAULT_PERMISSIONS = [
    ("admin:read",   "Read access to admin panel"),
    ("admin:write",  "Write access to admin panel"),
    ("admin:delete", "Delete access to admin panel"),
    ("admin:all",    "Full admin access"),
    ("users:read",   "Read user data"),
    ("users:write",  "Write user data"),
]

DEFAULT_ROLES = [
    ("admin",  "Full administrator access", ["admin:read", "admin:write", "admin:delete", "admin:all", "users:read", "users:write"]),
    ("user",   "Standard user",             ["users:read", "users:write"]),
    ("viewer", "Read-only access",          ["users:read", "admin:read"]),
]

ADMIN_EMAIL    = os.getenv("SEED_ADMIN_EMAIL",    "admin@authsystem.local")
ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "AdminPass123!")

DEMO_EMAIL    = os.getenv("SEED_DEMO_EMAIL",    "demo@authsystem.local")
DEMO_USERNAME = os.getenv("SEED_DEMO_USERNAME", "demouser")
DEMO_PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "DemoPass123!")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_or_create_permission(session: AsyncSession, name: str, description: str) -> Permission:
    result = await session.execute(select(Permission).where(Permission.name == name))
    perm = result.scalar()
    if not perm:
        perm = Permission(name=name, description=description)
        session.add(perm)
        await session.flush()
        print(f"  + permission: {name}")
    return perm


async def get_or_create_role(
    session: AsyncSession,
    name: str,
    description: str,
    perm_map: dict[str, Permission],
    perm_names: list[str],
) -> Role:
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(Role).where(Role.name == name).options(selectinload(Role.permissions))
    )
    role = result.scalar()
    if not role:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
        print(f"  + role: {name}")

    existing_perm_names = {p.name for p in role.permissions}
    for pname in perm_names:
        if pname in perm_map and pname not in existing_perm_names:
            role.permissions.append(perm_map[pname])

    return role


async def get_or_create_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
    full_name: str,
    is_superuser: bool,
    role: Role,
) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar()
    if not user:
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_verified=True,
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.flush()
        print(f"  + user: {email}  (password: {password})")
    else:
        print(f"  ~ user already exists: {email}")

    # Assign role if not already assigned
    result = await session.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if not result.scalar():
        session.add(UserRole(user_id=user.id, role_id=role.id))

    return user


# ── Main ──────────────────────────────────────────────────────────────────────

async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        print("\n── Permissions ──")
        perm_map: dict[str, Permission] = {}
        for pname, pdesc in DEFAULT_PERMISSIONS:
            perm_map[pname] = await get_or_create_permission(session, pname, pdesc)

        print("\n── Roles ──")
        role_map: dict[str, Role] = {}
        for rname, rdesc, rperms in DEFAULT_ROLES:
            role_map[rname] = await get_or_create_role(session, rname, rdesc, perm_map, rperms)

        print("\n── Users ──")
        await get_or_create_user(
            session,
            email=ADMIN_EMAIL,
            username=ADMIN_USERNAME,
            password=ADMIN_PASSWORD,
            full_name="Admin User",
            is_superuser=True,
            role=role_map["admin"],
        )
        await get_or_create_user(
            session,
            email=DEMO_EMAIL,
            username=DEMO_USERNAME,
            password=DEMO_PASSWORD,
            full_name="Demo User",
            is_superuser=False,
            role=role_map["user"],
        )

        await session.commit()

    await engine.dispose()
    print("\n✓ Seed complete.\n")
    print(f"  Admin  → {ADMIN_EMAIL}  /  {ADMIN_PASSWORD}")
    print(f"  Demo   → {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
    print("\n  Open http://localhost:8000/docs to explore the API.\n")


if __name__ == "__main__":
    asyncio.run(seed())
