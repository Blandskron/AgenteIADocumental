#!/usr/bin/env python3
"""Security and contract gate for optional AgentOrchestratorServices & CodeSandboxRunner (AG-034)."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    errors: list[str] = []

    agents_yml = yaml.safe_load((REPO_ROOT / "docker" / "compose" / "agents.yml").read_text(encoding="utf-8"))
    orch = agents_yml["services"]["agent-orchestrator-service"]
    orch_env = orch["environment"]
    if orch_env.get("AGENTS_ENABLED") != "${AGENTS_ENABLED:-false}":
        errors.append("agents.yml must default AGENTS_ENABLED to false.")
    if orch_env.get("CODE_MODE_ENABLED") != "${CODE_MODE_ENABLED:-false}":
        errors.append("agents.yml must default CODE_MODE_ENABLED to false.")
    if str(orch_env.get("LANGGRAPH_STRICT_MSGPACK", "")).lower() != "true":
        errors.append("agents.yml must enforce LANGGRAPH_STRICT_MSGPACK=true.")
    if orch.get("read_only") is not True or orch.get("cap_drop") != ["ALL"]:
        errors.append("agent-orchestrator-service must run read_only with cap_drop ALL.")
    if not str(orch.get("ports", [""])[0]).startswith("127.0.0.1:"):
        errors.append("agent-orchestrator-service must bind only to loopback 127.0.0.1.")

    code_yml = yaml.safe_load((REPO_ROOT / "docker" / "compose" / "code-mode.yml").read_text(encoding="utf-8"))
    if code_yml["networks"]["code_sandbox_net"].get("internal") is not True:
        errors.append("code_sandbox_net must be internal: true (no internet egress).")
    sandbox = code_yml["services"]["code-sandbox-runner"]
    if "ports" in sandbox:
        errors.append("code-sandbox-runner must NEVER publish host ports.")
    if "volumes" in sandbox:
        errors.append("code-sandbox-runner must NEVER mount host volumes.")
    if sandbox.get("read_only") is not True or sandbox.get("cap_drop") != ["ALL"]:
        errors.append("code-sandbox-runner must run read_only with cap_drop ALL.")

    if errors:
        for err in errors:
            print(f"CONTRACT ERROR: {err}", file=sys.stderr)
        return 1

    print("OK: AgentOrchestratorServices & CodeSandboxRunner security contracts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
