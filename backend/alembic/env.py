"""Alembic env (STEP 10B).

Nutzt dieselbe Engine-Konfiguration wie die App: URL aus
`app.core.config.settings.database_url` (backend/.env DATABASE_URL).
Target-Metadata = `app.database.base.Base.metadata` (alle Modelle).
"""

from __future__ import annotations

import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, ".")

from app.core.config import settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database import models  # noqa: E402,F401  (Modell-Registrierung)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline-Modus: DDL als SQL, ohne Verbindung."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online-Modus: DDL direkt auf der DB ausfuehren."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
