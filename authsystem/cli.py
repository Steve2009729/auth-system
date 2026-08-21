"""
AuthSystem CLI
==============

Commands:
    authsystem init          Scaffold .env, docker-compose.yml, and alembic config
    authsystem serve         Start the API server (dev defaults)
    authsystem create-admin  Interactively create a superuser
    authsystem migrate       Run database migrations (alembic upgrade head)
    authsystem --version     Print the version

Use  authsystem <command> --help  for per-command options.
"""
import os
import sys
import secrets
import subprocess
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="authsystem",
    help="AuthSystem — self-hosted FastAPI auth backend.",
    add_completion=False,
    no_args_is_help=True,
)

__version__ = "1.0.0"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    """Return the directory from which the CLI was invoked."""
    return Path.cwd()


def _require_env():
    """Ensure a .env file exists; remind user to create one if not."""
    env_path = _project_root() / ".env"
    if not env_path.exists():
        typer.echo(
            typer.style("✗ No .env file found.", fg=typer.colors.RED, bold=True)
        )
        typer.echo("  Run  authsystem init  to create one, then edit it.")
        raise typer.Exit(code=1)


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing .env file."),
):
    """
    Scaffold a .env file with a generated SECRET_KEY and dev-safe defaults.

    Safe to run in an existing project — it will not overwrite .env unless
    you pass --force.
    """
    root = _project_root()
    env_path = root / ".env"
    example_path = root / ".env.example"

    if env_path.exists() and not force:
        typer.echo(
            typer.style("✓ .env already exists", fg=typer.colors.GREEN)
            + " — skipping. Use --force to overwrite."
        )
    else:
        # Copy from example if available, otherwise create a minimal stub
        if example_path.exists():
            content = example_path.read_text()
        else:
            content = (
                "APP_NAME=AuthSystem\n"
                "DEBUG=true\n"
                "SECRET_KEY=\n"
                "DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/authdb\n"
                "REDIS_URL=redis://localhost:6379/0\n"
            )

        # Inject a freshly generated SECRET_KEY
        key = secrets.token_hex(64)
        if "SECRET_KEY=" in content:
            lines = []
            for line in content.splitlines():
                if line.startswith("SECRET_KEY="):
                    lines.append(f"SECRET_KEY={key}")
                else:
                    lines.append(line)
            content = "\n".join(lines) + "\n"
        else:
            content += f"\nSECRET_KEY={key}\n"

        env_path.write_text(content)
        typer.echo(typer.style("✓ Created .env", fg=typer.colors.GREEN))
        typer.echo(f"  SECRET_KEY has been generated and written to .env")

    typer.echo("\nNext steps:")
    typer.echo("  1. Start Postgres + Redis:  docker-compose up -d db redis")
    typer.echo("  2. Run migrations:           authsystem migrate")
    typer.echo("  3. Seed default data:        python scripts/seed.py")
    typer.echo("  4. Start the server:         authsystem serve")
    typer.echo("  5. Open the docs:            http://localhost:8000/docs\n")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port."),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable auto-reload (dev)."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes (prod; disables reload)."),
):
    """
    Start the AuthSystem API server.

    Runs with hot-reload by default (good for development). Pass --no-reload
    and --workers N for a production-style start.
    """
    _require_env()

    try:
        import uvicorn
    except ImportError:
        typer.echo(typer.style("✗ uvicorn is not installed.", fg=typer.colors.RED))
        typer.echo("  Run:  pip install authsystem-fastapi")
        raise typer.Exit(code=1)

    typer.echo(
        typer.style(f"▶  Starting AuthSystem on http://{host}:{port}", fg=typer.colors.GREEN, bold=True)
    )
    typer.echo(f"   Docs → http://localhost:{port}/docs\n")

    use_reload = reload and workers == 1
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=use_reload,
        workers=None if use_reload else workers,
    )


@app.command("create-admin")
def create_admin(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Admin email address."),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Admin username."),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Admin password (prompted if omitted)."),
):
    """
    Create a superuser account interactively.

    If --email, --username, or --password are omitted you will be prompted.
    The database must be running and migrated before calling this command.
    """
    _require_env()

    if not email:
        email = typer.prompt("Admin email")
    if not username:
        username = typer.prompt("Admin username", default=email.split("@")[0])
    if not password:
        password = typer.prompt("Admin password", hide_input=True, confirmation_prompt=True)

    if len(password) < 8:
        typer.echo(typer.style("✗ Password must be at least 8 characters.", fg=typer.colors.RED))
        raise typer.Exit(code=1)

    import asyncio

    async def _create():
        # Load app settings (validates env)
        from dotenv import load_dotenv
        load_dotenv()

        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select
        from app.config import settings
        from app.models.user import User
        from app.models.role import Role, UserRole
        from app.core.security import hash_password as _hash

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with maker() as session:
            # Check for duplicate
            result = await session.execute(select(User).where(User.email == email))
            if result.scalar():
                typer.echo(typer.style(f"✗ A user with email {email} already exists.", fg=typer.colors.RED))
                raise typer.Exit(code=1)

            user = User(
                email=email,
                username=username,
                hashed_password=_hash(password),
                full_name="Admin",
                is_verified=True,
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            await session.flush()

            # Assign admin role if it exists
            result = await session.execute(select(Role).where(Role.name == "admin"))
            role = result.scalar()
            if role:
                session.add(UserRole(user_id=user.id, role_id=role.id))

            await session.commit()

        await engine.dispose()
        typer.echo(typer.style(f"\n✓ Superuser created: {email}", fg=typer.colors.GREEN, bold=True))
        typer.echo(f"  Login at http://localhost:8000/docs → POST /auth/login\n")

    asyncio.run(_create())


@app.command()
def migrate(
    revision: str = typer.Argument("head", help="Alembic revision target (default: head)."),
    autogenerate: bool = typer.Option(False, "--autogenerate", "-a", help="Auto-generate a new migration."),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Migration message (used with --autogenerate)."),
):
    """
    Run database migrations via Alembic.

    By default runs  alembic upgrade head.
    Use --autogenerate -m "description"  to generate a new migration file.
    """
    _require_env()

    if autogenerate:
        msg = message or "auto migration"
        cmd = ["alembic", "revision", "--autogenerate", "-m", msg]
        typer.echo(f"Generating migration: {msg}")
    else:
        cmd = ["alembic", "upgrade", revision]
        typer.echo(f"Running: alembic upgrade {revision}")

    result = subprocess.run(cmd, cwd=str(_project_root()))
    if result.returncode != 0:
        typer.echo(typer.style("✗ Migration failed.", fg=typer.colors.RED))
        raise typer.Exit(code=result.returncode)

    typer.echo(typer.style("✓ Migration complete.", fg=typer.colors.GREEN))


def version_callback(value: bool):
    if value:
        typer.echo(f"authsystem {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-V",
        callback=version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
):
    """AuthSystem CLI — manage your self-hosted auth backend."""


if __name__ == "__main__":
    app()
