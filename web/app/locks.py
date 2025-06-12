import asyncio, os, time, uuid

import aioredis
from fastapi import HTTPException

# ---------------------------------------------------------------------------
#  Redis connection (shared pooled client)
# ---------------------------------------------------------------------------

REDIS_DSN = os.getenv("REDIS_DSN", "redis://redis:6379/0")
_redis = aioredis.from_url(REDIS_DSN, encoding="utf-8", decode_responses=True)

# ---------------------------------------------------------------------------
#  Seat-locking helper
# ---------------------------------------------------------------------------

class SeatLock:
    """Async context-manager that obtains a short-lived Redis lock per departure.

    Usage::
        async with SeatLock(dep_id):
            # safe to run capacity checks & INSERT booking

    – Locks automatically expire after *ttl* seconds so that abandoned
      sessions don't dead-lock seats indefinitely.
    """

    def __init__(self, departure_id: int, ttl: int = 300, retry_delay: float = 0.1, timeout: float = 5.0):
        self.key = f"lock:dep:{departure_id}"
        self.ttl = ttl
        self._retry_delay = retry_delay
        self._timeout = timeout
        self._token = uuid.uuid4().hex  # unique owner id

    async def __aenter__(self):
        start = time.time()
        # Redis SET … NX EX implements a simple mutex
        while True:
            ok = await _redis.set(self.key, self._token, ex=self.ttl, nx=True)
            if ok:
                return self
            if time.time() - start > self._timeout:
                raise HTTPException(409, "Another user is currently booking these seats, please retry in a moment")
            await asyncio.sleep(self._retry_delay)

    async def __aexit__(self, exc_type, exc, tb):
        # Delete the lock *only* if we still own it (avoid race conditions)
        if (await _redis.get(self.key)) == self._token:
            await _redis.delete(self.key) 