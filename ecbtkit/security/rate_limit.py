"""
Rate limiter with optional Redis backend (shared across workers).

Falls back to in-process memory if Redis is unavailable — fail-safe, never
blocks the app from starting.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import RateLimitError

logger = logging.getLogger("ecbtkit.ratelimit")


class _MemoryBackend:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window: int) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                retry = int(window - (now - q[0])) + 1
                raise RateLimitError(retry_after=max(1, retry))
            q.append(now)
            # light cleanup
            if len(self._hits) > 50_000:
                stale = [k for k, v in self._hits.items() if not v or v[-1] <= now - window]
                for k in stale[:1000]:
                    self._hits.pop(k, None)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


class _RedisBackend:
    def __init__(self, url: str):
        import redis  # optional dependency

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1.0)
        self._r.ping()

    def check(self, key: str, limit: int, window: int) -> None:
        # Sliding window via sorted set
        now = time.time()
        pipe = self._r.pipeline()
        member = f"{now}"
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = pipe.execute()
        count = results[2]
        if count > limit:
            raise RateLimitError(retry_after=window)

    def reset(self, key: str) -> None:
        self._r.delete(key)


class RateLimiter:
    def __init__(self) -> None:
        self._backend = None
        self._memory = _MemoryBackend()

    def _get_backend(self):
        if self._backend is not None:
            return self._backend
        settings = get_settings()
        url = getattr(settings, "redis_url", None)
        if url:
            try:
                self._backend = _RedisBackend(url)
                logger.info("rate_limit.backend=redis")
                return self._backend
            except Exception as exc:
                logger.warning("rate_limit.redis_unavailable fallback=memory error=%s", type(exc).__name__)
        self._backend = self._memory
        return self._backend

    def check(
        self,
        key: str,
        *,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = limit if limit is not None else settings.rate_limit_requests
        window = window if window is not None else settings.rate_limit_window_seconds
        try:
            self._get_backend().check(key, limit, window)
        except RateLimitError:
            raise
        except Exception:
            # Fail open if backend errors mid-request
            logger.warning("rate_limit.check_failed fail_open=true")

    def reset(self, key: str) -> None:
        try:
            self._get_backend().reset(key)
        except Exception:
            pass


limiter = RateLimiter()


def client_key(ip: str, route: str = "") -> str:
    return f"{ip}:{route}" if route else ip
