"""In-memory and PostgreSQL-friendly tenant daily token quota & concurrency guard for Knowledge Studio (R7-03)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class TenantQuotaUsage:
    day: date
    tokens_used: int = 0
    active_jobs: int = 0


class QuotaExceededError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class StudioQuotaGuard:
    """Enforces per-tenant daily token budgets and concurrent job caps to prevent LLM cost spikes."""

    def __init__(self, *, daily_token_limit: int = 200_000, max_concurrent_jobs: int = 3) -> None:
        self._daily_token_limit = max(1, daily_token_limit)
        self._max_concurrent_jobs = max(1, max_concurrent_jobs)
        self._usage: dict[str, TenantQuotaUsage] = {}

    def _entry(self, tenant_id: str, today: date | None = None) -> TenantQuotaUsage:
        day = today or date.today()
        current = self._usage.get(tenant_id)
        if current is None or current.day != day:
            current = TenantQuotaUsage(day=day)
            self._usage[tenant_id] = current
        return current

    def acquire_job_slot(self, tenant_id: str, estimated_tokens: int = 0, today: date | None = None) -> None:
        entry = self._entry(tenant_id, today=today)
        if entry.active_jobs >= self._max_concurrent_jobs:
            raise QuotaExceededError("CONCURRENCY_LIMIT", "Límite de jobs simultáneos de Studio alcanzado para la empresa.")
        if entry.tokens_used + max(0, estimated_tokens) > self._daily_token_limit:
            raise QuotaExceededError("DAILY_TOKEN_QUOTA", "Cuota diaria de tokens de Studio agotada para la empresa.")
        entry.active_jobs += 1

    def release_job_slot(self, tenant_id: str, actual_tokens: int = 0, today: date | None = None) -> None:
        entry = self._entry(tenant_id, today=today)
        entry.active_jobs = max(0, entry.active_jobs - 1)
        entry.tokens_used += max(0, actual_tokens)

    def remaining_tokens(self, tenant_id: str, today: date | None = None) -> int:
        entry = self._entry(tenant_id, today=today)
        return max(0, self._daily_token_limit - entry.tokens_used)

