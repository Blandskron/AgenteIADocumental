#!/usr/bin/env python3
"""Live local performance & health budget probe for Blandskron Documental (STB-09).

Measures real HTTP response latencies against a running Docker Compose stack.
Never invents metrics when the stack is not running.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENDPOINTS = {
    "frontend": "http://127.0.0.1:3000/",
    "auth_setup_status": "http://127.0.0.1:8001/api/users/setup-status/",
    "rag_chat_health": "http://127.0.0.1:8002/api/v1/health/db",
    "embedding_health": "http://127.0.0.1:8003/api/v1/health/db",
    "search_health": "http://127.0.0.1:8004/api/v1/health/db",
    "access_health": "http://127.0.0.1:8005/api/v1/health/db",
    "library_health": "http://127.0.0.1:8006/api/v1/health/db",
}


def probe(url: str, timeout: float = 3.0) -> dict:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            return {"reachable": True, "status_code": resp.status, "latency_ms": elapsed_ms}
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"reachable": False, "error": str(exc)[:160], "latency_ms": elapsed_ms}


def main() -> int:
    measurements = {name: probe(url) for name, url in ENDPOINTS.items()}
    any_up = any(m["reachable"] for m in measurements.values())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stack_running": any_up,
        "measurements": measurements,
    }
    out_dir = ROOT / ".release-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "PERFORMANCE_BUDGET.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Performance probe complete (stack_running={any_up}) -> {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

