"""Tiny in-process TTL cache, invalidated when the pipeline bumps
meta.data_version. Good enough for a single-process research deployment; swap
for Redis if you scale to multiple workers.

Because the store below is per-process, this cache is only coherent with a
single worker. `WEB_CONCURRENCY` therefore defaults to 1 (entrypoint.sh,
docker-compose.yml, .env.example); raising it requires a shared cache first.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_store: dict[str, tuple[float, str, Any]] = {}  # key -> (expires_at, data_version, value)


async def get_data_version(session: AsyncSession) -> str:
    row = await session.execute(text("SELECT value FROM meta WHERE key = 'data_version'"))
    val = row.scalar_one_or_none()
    return val or "0"


async def cached(key: str, session: AsyncSession, producer: Callable[[], Awaitable[Any]]) -> Any:
    """Return producer() result, memoized by (key, data_version) for cache_ttl."""
    version = await get_data_version(session)
    now = time.monotonic()
    hit = _store.get(key)
    if hit and hit[0] > now and hit[1] == version:
        return hit[2]
    value = await producer()
    _store[key] = (now + settings.cache_ttl_seconds, version, value)
    return value


def clear() -> None:
    _store.clear()
