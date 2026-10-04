"""Alembic environment — uses ECBT_DATABASE_URL from settings."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Prefer environment / eCBTKit settings
url = os.getenv("ECBT_DATABASE_URL") or os.getenv("DATABASE_URL")
if url:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("mysql://") and "+pymysql" not in url:
        url = "mysql+pymysql://" + url[len("mysql://"):]
    config.set_main_option("sqlalchemy.url", url)

from ecbtkit.db.base import Base  # noqa: E402
from ecbtkit.models import *  # noqa: F401,F403,E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
