"""Per-tenant active concurrency guard preventing CPU/Ollama saturation (AG-040)."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import os
import threading
from typing import Iterator


class ConcurrencyLimitError(RuntimeError):
    """Raised when a tenant already has the maximum number of active agent runs (HTTP 429)."""


class TenantConcurrencyGuard:
    """Thread-safe active run counter per tenant with deterministic try/finally release."""

    def __init__(self, *, max_concurrent_per_tenant: int | None = None) -> None:
        self._limit = (
            max_concurrent_per_tenant
            if max_concurrent_per_tenant is not None
            else int(os.environ.get("AGENT_MAX_CONCURRENT_RUNS_PER_TENANT", "3"))
        )
        self._lock = threading.Lock()
        self._active: Counter[str] = Counter()

    def active_count(self, tenant_id: str) -> int:
        with self._lock:
            return int(self._active.get(tenant_id, 0))

    @contextmanager
    def acquire(self, tenant_id: str) -> Iterator[int]:
        with self._lock:
            current = self._active[tenant_id]
            if current >= self._limit:
                raise ConcurrencyLimitError(
                    f"Demasiadas ejecuciones agénticas simultáneas ({current}/{self._limit}) para este tenant."
                )
            self._active[tenant_id] = current + 1
            in_flight = self._active[tenant_id]
        try:
            yield in_flight
        finally:
            with self._lock:
                if self._active[tenant_id] > 0:
                    self._active[tenant_id] -= 1
