"""
Rate limiter — in-memory for development; Redis required in multi-worker production.
"""

from __future__ import annotations

import logging
import time
import uuid
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

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def ping(self) -> bool:
        return True


class _RedisBackend:
    def __init__(self, url: str):
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5)
        self._r.ping()

    def check(self, key: str, limit: int, window: int) -> None:
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex}"
        pipe = self._r.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = pipe.execute()
        count = int(results[2])
        if count > limit:
            raise RateLimitError(retry_after=window)

    def reset(self, key: str) -> None:
        self._r.delete(key)

    def ping(self) -> bool:
        return bool(self._r.ping())


class RateLimiter:
    def __init__(self) -> None:
        self._backend = None
        self._init_error: Optional[str] = None

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
                self._init_error = type(exc).__name__
                logger.error("rate_limit.redis_unavailable error=%s", self._init_error)
                if settings.is_production:
                    raise RuntimeError(
                        "Redis rate limiter required in production but unavailable: "
                        f"{self._init_error}"
                    ) from exc
                logger.warning("rate_limit.fallback=memory (non-production)")
        elif settings.is_production and settings.rate_limit_enabled:
            raise RuntimeError(
                "ECBT_REDIS_URL is required in production when rate limiting is enabled"
            )
        self._backend = _MemoryBackend()
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
        backend = self._get_backend()
        try:
            backend.check(key, limit, window)
        except RateLimitError:
            raise
        except Exception as exc:
            if settings.is_production:
                raise RateLimitError(
                    message="Rate limiter unavailable",
                    retry_after=60,
                ) from exc
            logger.warning("rate_limit.check_failed fail_open=dev error=%s", type(exc).__name__)

    def reset(self, key: str) -> None:
        try:
            self._get_backend().reset(key)
        except Exception:
            pass


limiter = RateLimiter()


def client_key(ip: str, route: str = "") -> str:
    return f"{ip}:{route}" if route else ip
