from __future__ import annotations

from app.application.metrics_service import AgentMetricsCollector


def test_metrics_collector_aggregates_per_tenant_without_cross_tenant_leakage() -> None:
    collector = AgentMetricsCollector()
    collector.record_run_outcome(
        tenant_id="tenant-a",
        status="SUCCEEDED",
        provider="ollama",
        steps_used=3,
        usage_tokens=1200,
        code_mode_used=True,
        duration_ms=420,
    )
    collector.record_run_outcome(
        tenant_id="tenant-a",
        status="CANCELLED",
        provider="groq",
        steps_used=1,
        usage_tokens=300,
        code_mode_used=False,
        duration_ms=180,
    )
    collector.record_run_outcome(
        tenant_id="tenant-b",
        status="SUCCEEDED",
        provider="groq",
        steps_used=2,
        usage_tokens=900,
    )

    snap_a = collector.snapshot("tenant-a")
    snap_b = collector.snapshot("tenant-b")

    assert snap_a["total_runs"] == 2
    assert snap_a["runs_by_status"] == {"SUCCEEDED": 1, "CANCELLED": 1}
    assert snap_a["runs_by_provider"] == {"ollama": 1, "groq": 1}
    assert snap_a["code_mode_runs"] == 1
    assert snap_a["total_tokens"] == 1500
    assert snap_a["avg_duration_ms"] == 300.0

    assert snap_b["total_runs"] == 1
    assert snap_b["total_tokens"] == 900
