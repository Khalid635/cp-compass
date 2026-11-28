"""Alembic environment: the URL comes from app.config
(MIGRATION_DATABASE_URL — the owner-role connection; falls back to
DATABASE_URL when unset), and autogenerate reads the models' MetaData.
Works for SQLite (local dev) and Postgres (Neon) — the models use no
Postgres-specific types.

Batch 6, reel #3: migrations must run as the owner role even after the
runtime switches to the least-privilege cpcompass_app role, so Alembic
never uses the runtime DATABASE_URL directly."""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app` importable when alembic runs from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import MIGRATION_DATABASE_URL  # noqa: E402
from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401  (import registers the tables)

config = context.config
# Use the owner-role URL only when no real URL was supplied: alembic.ini
# ships the stock placeholder, and callers (tests) may set a URL on the
# Config object. Overwriting unconditionally sent migrations to the wrong
# database (broke test_migration_0008_roundtrip in Batch 6).
if config.get_main_option("sqlalchemy.url") in (None, "",
        "driver://user:pass@localhost/dbname"):
    config.set_main_option("sqlalchemy.url", MIGRATION_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
