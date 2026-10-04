"""
In-memory sliding-window rate limiter.

For multi-process / multi-host production, swap the store for Redis
(install ecbtkit[redis] and set ECBT_REDIS_URL).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional, Tuple

from ecbtkit.core.config import get_settings
from ecbtkit.core.exceptions import RateLimitError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

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


# Process-wide default instance
limiter = RateLimiter()


def client_key(ip: str, route: str = "") -> str:
    return f"{ip}:{route}" if route else ip
