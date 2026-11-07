"""Sliding-window rate limiting for a single API process.

Limits are kept in memory, so they are per-process. A multi-replica deployment needs a
shared store (Redis); that limitation is documented in docs/security.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int, float]:
        """Record a hit. Returns (allowed, remaining, retry_after_seconds)."""
        if self.limit <= 0:
            return True, self.limit, 0.0
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(0.0, hits[0] + self.window_seconds - current)
                return False, 0, retry_after
            hits.append(current)
            return True, self.limit - len(hits), 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
