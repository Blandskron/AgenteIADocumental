#!/usr/bin/env python3
"""Deterministic local performance budget benchmark for AgentOrchestratorServices (AG-024).

Measures orchestration overhead without external API keys:
- Strict checkpoint compaction & serialization latency
- Grounded citation verification & pruning latency
- Deterministic date/amount extraction latency
- Sandbox static escape-policy validation latency
Writes JSON evidence to .release-reports/AGENTS_BENCHMARK.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "AgentOrchestratorServices"))

from app.application.graph.research_graph import verify_and_prune_citations  # noqa: E402
from app.application.templates.agent_templates import extract_deterministic_facts  # noqa: E402
from app.infrastructure.database.checkpointer import compact_checkpoint_state  # noqa: E402
from app.infrastructure.sandbox.sandbox_client import validate_sandbox_script  # noqa: E402


def _measure_ms(fn, iterations: int = 200) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return round(elapsed_ms / iterations, 4)


def main() -> int:
    evidence = [
        {
            "document_id": f"doc-{i:03d}",
            "chunk_index": i % 5,
            "filename": f"contrato_{i:03d}.pdf",
            "quote": f"Cláusula {i}: vencimiento 2027-06-30, importe USD 12,500.00 y recargo del 2.5% mensual.",
        }
        for i in range(1, 25)
    ]
    sample_state = {
        "run_id": "run_bench",
        "thread_id": "thr_bench",
        "goal": "Comparar cláusulas y vencimientos",
        "evidence": evidence,
        "steps": [{"index": i, "tool": "search_documents", "status": "ok", "duration_ms": 15} for i in range(1, 6)],
    }
    sample_md = " ".join(f"Hallazgo {i} [Fuente {i}]." for i in range(1, 20)) + " Extra [Fuente 99]."
    sample_code = "function transform(data) { return { total: data.evidence.length }; }"

    metrics = {
        "checkpoint_compact_avg_ms": _measure_ms(lambda: compact_checkpoint_state(sample_state)),
        "citation_verify_avg_ms": _measure_ms(lambda: verify_and_prune_citations(sample_md, evidence)),
        "facts_extract_avg_ms": _measure_ms(lambda: extract_deterministic_facts(evidence)),
        "sandbox_policy_validate_avg_ms": _measure_ms(lambda: validate_sandbox_script(sample_code)),
    }

    budgets_ms = {
        "checkpoint_compact_avg_ms": 10.0,
        "citation_verify_avg_ms": 5.0,
        "facts_extract_avg_ms": 10.0,
        "sandbox_policy_validate_avg_ms": 5.0,
    }
    passed = all(metrics[k] <= budgets_ms[k] for k in budgets_ms)

    report = {
        "status": "PASS" if passed else "FAIL",
        "metrics_ms": metrics,
        "budgets_ms": budgets_ms,
    }
    out_dir = REPO_ROOT / ".release-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "AGENTS_BENCHMARK.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
