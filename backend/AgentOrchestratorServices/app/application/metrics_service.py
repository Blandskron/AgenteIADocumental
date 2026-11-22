"""Operational telemetry & non-sensitive metrics aggregator for AgentOrchestratorServices (AG-019)."""

from __future__ import annotations

from collections import Counter
from typing import Any


class AgentMetricsCollector:
    """Collects per-tenant operational metrics without storing PII or document snippets."""

    def __init__(self) -> None:
        self._runs_by_status: dict[str, Counter[str]] = {}
        self._runs_by_provider: dict[str, Counter[str]] = {}
        self._code_mode_runs: Counter[str] = Counter()
        self._total_tokens: Counter[str] = Counter()
        self._total_steps: Counter[str] = Counter()
        self._latency_ms_sum: Counter[str] = Counter()
        self._latency_samples: Counter[str] = Counter()

    def record_run_outcome(
        self,
        *,
        tenant_id: str,
        status: str,
        provider: str | None,
        steps_used: int,
        usage_tokens: int,
        code_mode_used: bool = False,
        duration_ms: int = 0,
    ) -> None:
        self._runs_by_status.setdefault(tenant_id, Counter())[status] += 1
        self._runs_by_provider.setdefault(tenant_id, Counter())[provider or "unknown"] += 1
        if code_mode_used:
            self._code_mode_runs[tenant_id] += 1
        self._total_tokens[tenant_id] += max(0, int(usage_tokens))
        self._total_steps[tenant_id] += max(0, int(steps_used))
        if duration_ms > 0:
            self._latency_ms_sum[tenant_id] += int(duration_ms)
            self._latency_samples[tenant_id] += 1

    def snapshot(self, tenant_id: str) -> dict[str, Any]:
        statuses = dict(self._runs_by_status.get(tenant_id, Counter()))
        providers = dict(self._runs_by_provider.get(tenant_id, Counter()))
        samples = self._latency_samples.get(tenant_id, 0)
        avg_latency = round(self._latency_ms_sum.get(tenant_id, 0) / samples, 1) if samples else 0.0
        return {
            "tenant_id": tenant_id,
            "total_runs": sum(statuses.values()),
            "runs_by_status": statuses,
            "runs_by_provider": providers,
            "code_mode_runs": self._code_mode_runs.get(tenant_id, 0),
            "total_tokens": self._total_tokens.get(tenant_id, 0),
            "total_steps": self._total_steps.get(tenant_id, 0),
            "avg_duration_ms": avg_latency,
        }
