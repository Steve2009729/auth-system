"""Alembic environment configuration."""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_url(url: str) -> str:
    """Convert async driver URL to sync for Alembic."""
    return url.replace("+asyncpg", "")


# Set sqlalchemy.url from environment
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option(
        "sqlalchemy.url",
        _sync_url(os.getenv("DATABASE_URL", "postgresql://user:password@localhost/authdb"))
    )

# add your model's MetaData object here
from app.db.base import Base
import app.models  # register all models with Base.metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _sync_url(
        os.getenv("DATABASE_URL", "postgresql://user:password@localhost/authdb")
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

