"""asyncpg connection pool for the activity domain.

One pool per process, opened on FastAPI lifespan startup. Routes acquire
connections via `async with pool.acquire() as conn`.

The pool is intentionally tiny (min=1, max=10) — activity routes are
short-lived and Railway's Postgres add-on starts on the Hobby plan with
a low connection ceiling. Bump `ACTIVITY_DB_POOL_MAX` if a future tier
needs more.
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Reference the Railway Postgres service's "
            "DATABASE_URL variable into the Prophet app service (Variables → "
            "Add Reference). Never use DATABASE_PUBLIC_URL from the app."
        )
    # asyncpg dislikes the `postgresql+asyncpg://` SQLAlchemy prefix some
    # providers hand out; strip it to the plain scheme.
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def open_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # `timeout=5.0` is the per-connection-attempt timeout (asyncpg's
        # default is None — wait forever). Without this, a misconfigured
        # DATABASE_URL hangs FastAPI's lifespan indefinitely and the whole
        # site goes dark instead of just the activity routes.
        _pool = await asyncpg.create_pool(
            dsn=_database_url(),
            min_size=1,
            max_size=int(os.getenv("ACTIVITY_DB_POOL_MAX", "10")),
            timeout=5.0,
            command_timeout=5.0,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Synchronous accessor for handlers — pool must already be open."""
    if _pool is None:
        raise RuntimeError(
            "activity db pool not initialised; call open_pool() in lifespan."
        )
    return _pool
