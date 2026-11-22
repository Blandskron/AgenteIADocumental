#!/usr/bin/env python3
"""Single-command local verification runner for the Agentic AI stack (AG-044)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], *, env_extra: dict[str, str] | None = None) -> None:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    print(f"==> {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> int:
    py = sys.executable
    _run(
        [
            py,
            "-m",
            "ruff",
            "check",
            "--select",
            "F,E721,W",
            "backend/AgentOrchestratorServices/app",
            "backend/AgentOrchestratorServices/tests",
            "backend/CodeSandboxRunner/tests",
            "scripts/ci/check_agents_contract.py",
            "scripts/ci/verify_agents_all.py",
            "scripts/eval/benchmark_agents_budget.py",
        ]
    )
    _run([py, "scripts/ci/check_agents_contract.py"])
    _run([py, "scripts/eval/benchmark_agents_budget.py"])
    _run(
        [
            py,
            "-m",
            "pytest",
            "-q",
            "backend/AgentOrchestratorServices/tests",
            "backend/CodeSandboxRunner/tests",
        ],
        env_extra={"PYTHONPATH": str(REPO_ROOT / "backend" / "AgentOrchestratorServices")},
    )
    _run([py, "scripts/ci/check_docs_links.py"])
    print("OK: All Agentic AI backend, sandbox, contract, benchmark and docs checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
