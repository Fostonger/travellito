from __future__ import annotations

"""Alembic environment configured for *async* migrations.

Usage:
    # Generate new migration after editing models
    alembic revision --autogenerate -m "<message>"

    # Apply all pending migrations
    alembic upgrade head

Alembic reads its config from `web/alembic.ini` (script_location = web/migrations).
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
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

async def run_migrations_online() -> None:
    """Run migrations with an *async* DB engine."""

    connectable = create_async_engine(DB_DSN, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(connection=conn, target_metadata=target_metadata)
        )

        async with context.begin_transaction():
            await context.run_migrations()

    await connectable.dispose()


def run():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


run() 