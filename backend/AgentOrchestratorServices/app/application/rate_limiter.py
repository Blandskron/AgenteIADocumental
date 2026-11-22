"""Sliding-window per-(tenant, user) rate limiter for agent runs (AG-030)."""

from __future__ import annotations

from collections import deque
import os
from time import monotonic


class RateLimitExceededError(RuntimeError):
    """Raised when a user exceeds the allowed agent run creation rate (HTTP 429)."""

    def __init__(self, retry_after_seconds: int, message: str) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, retry_after_seconds)


class AgentRateLimiter:
    """In-memory sliding-window rate limiter keyed by (tenant_id, user_id)."""

    def __init__(
        self,
        *,
        max_requests: int | None = None,
        window_seconds: float = 60.0,
    ) -> None:
        self._max_requests = (
            max_requests
            if max_requests is not None
            else int(os.environ.get("AGENT_RATE_LIMIT_PER_MINUTE", "20"))
        )
        self._window_seconds = max(1.0, float(window_seconds))
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    def check_and_record(
        self,
        *,
        tenant_id: str,
        user_id: str,
        now: float | None = None,
    ) -> int:
        """Records a request or raises RateLimitExceededError with Retry-After seconds. Returns remaining slots."""
        ts = monotonic() if now is None else float(now)
        key = (tenant_id, user_id)
        bucket = self._buckets.setdefault(key, deque())
        cutoff = ts - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self._max_requests:
            retry_after = int(max(1.0, (bucket[0] + self._window_seconds) - ts)) + 1
            raise RateLimitExceededError(
                retry_after_seconds=retry_after,
                message=(
                    f"Límite de velocidad excedido ({self._max_requests} ejecuciones por "
                    f"{int(self._window_seconds)}s). Reintenta en {retry_after}s."
                ),
            )
        bucket.append(ts)
        return max(0, self._max_requests - len(bucket))

    def reset(self) -> None:
        self._buckets.clear()
