"""Optional Code Mode graph node with progressive tool discovery (AG-011)."""

from __future__ import annotations

import os
from typing import Any

from app.application.tools.registry import ToolRegistry
from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.sandbox.sandbox_client import SandboxHttpClient


class CodeModeDisabledError(RuntimeError):
    """Raised when enable_code_mode=true is requested while CODE_MODE_ENABLED=false (HTTP 503)."""

    code = "CODE_MODE_DISABLED"


def is_code_mode_enabled() -> bool:
    return os.environ.get("CODE_MODE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def discover_readonly_tools(registry: ToolRegistry, query: str = "") -> list[dict[str, Any]]:
    """Progressive discovery (`search`): returns compact metadata for read-only tools matching query."""
    needle = (query or "").strip().lower()
    results = []
    for spec in registry.list_specs():
        if not spec.get("read_only"):
            continue
        haystack = f"{spec['name']} {spec['description']}".lower()
        if not needle or needle in haystack:
            results.append({"name": spec["name"], "description": spec["description"]})
    return results


def describe_readonly_tool(registry: ToolRegistry, tool_name: str) -> dict[str, Any] | None:
    """Progressive discovery (`describe`): returns full JSON Schema for a single read-only tool."""
    for spec in registry.list_specs():
        if spec["name"] == tool_name and spec.get("read_only"):
            return {
                "name": spec["name"],
                "description": spec["description"],
                "input_schema": spec["input_schema"],
                "max_results": spec["max_results"],
            }
    return None


def execute_code_mode_node(
    *,
    code: str,
    evidence: list[dict[str, Any]],
    sandbox_client: SandboxHttpClient,
    audit_logger: AuditLogger,
    tenant_id: str,
    actor_user_id: str,
    run_id: str,
    enforce_env_flag: bool = True,
) -> dict[str, Any]:
    """Executes deterministic data transformation over retrieved evidence inside the hardened sandbox."""
    if enforce_env_flag and not is_code_mode_enabled():
        raise CodeModeDisabledError("Code Mode está deshabilitado (CODE_MODE_ENABLED=false).")

    # Only pass sanitized evidence references & snippets — never tokens or user credentials
    sandbox_data = {
        "evidence": [
            {
                "document_id": str(item.get("document_id") or ""),
                "chunk_index": int(item.get("chunk_index") or 0),
                "filename": str(item.get("filename") or ""),
                "quote": str(item.get("quote") or ""),
            }
            for item in evidence
        ]
    }
    execution = sandbox_client.execute(code=code, data=sandbox_data)
    audit_logger.record(
        event_type="agent.code_mode.executed",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        run_id=run_id,
        metadata={
            "code_bytes": len(code.encode("utf-8")),
            "evidence_count": len(evidence),
            "duration_ms": execution["duration_ms"],
            "ok": execution["ok"],
        },
    )
    return {
        "code": code,
        "output": execution["output"],
        "stdout": execution["stdout"],
        "duration_ms": execution["duration_ms"],
        "evidence_count": len(evidence),
    }
