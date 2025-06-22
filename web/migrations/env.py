from __future__ import annotations

"""Alembic environment configured for *async* migrations.

Usage:
    # Generate new migration after editing models
    alembic revision --autogenerate -m "<message>"

    # Apply all pending migrations
    alembic upgrade head

Alembic reads its config from `web/alembic.ini` (script_location = web/migrations).
"""

import os, sys, re
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# ---------------------------------------------------------------------------
#  Make sure `import app` works when env.py is executed from the project root
# ---------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Import metadata from the application
from app.models import Base  # noqa: E402
from app.deps import DB_DSN  # noqa: E402

# ---------------------------------------------------------------------------
#  Alembic Config object & logging
# ---------------------------------------------------------------------------
config = context.config

# Convert asyncpg URL to sync for Alembic
SYNC_DSN = re.sub(r"\+asyncpg", "", DB_DSN, count=1)
config.set_main_option("sqlalchemy.url", SYNC_DSN)

fileConfig(config.config_file_name)

target_metadata = Base.metadata  # models metadata for `--autogenerate`


# ---------------------------------------------------------------------------
#  Helper: offline migration (generate SQL scripts only)
# ---------------------------------------------------------------------------

def run_migrations_offline():
    """Run migrations without DB connection (generates raw SQL)."""
    url = DB_DSN
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
#  Helper: online migration (apply directly to DB)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    """Run migrations inside a synchronous transaction (avoids greenlet errors)."""

    connectable = create_engine(SYNC_DSN, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


def run():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()


run() 