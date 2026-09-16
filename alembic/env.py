"""Alembic environment. The database URL comes from settings (or ENOLA_ALEMBIC_URL
for the test database); models are imported so autogenerate sees every table."""

from __future__ import annotations

import os
from logging.config import fileConfig

import pgvector.sqlalchemy  # noqa: F401  (so autogenerate can render Vector columns)
from alembic import context
from sqlalchemy import engine_from_config, pool

import enola.core.models  # noqa: F401  (registers all tables on Base.metadata)
from enola.core.config import get_settings
from enola.core.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return os.environ.get("ENOLA_ALEMBIC_URL") or get_settings().database_url


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Render pgvector's Vector type with its import in generated migrations."""
    if type_ == "type" and obj.__class__.__name__ == "VECTOR":
        autogen_context.imports.add("import pgvector.sqlalchemy")  # type: ignore[attr-defined]
        return f"pgvector.sqlalchemy.Vector({getattr(obj, 'dim', None)})"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
