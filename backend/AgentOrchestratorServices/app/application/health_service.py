"""Deep dependency health probe for AgentOrchestratorServices (AG-035)."""

from __future__ import annotations

import json
import os
from typing import Any
import urllib.request

from app.application.tools.registry import redact_secrets


def _probe_http(url: str, *, timeout: float = 2.5, transport: Any | None = None) -> dict[str, Any]:
    if transport is not None:
        return transport(url, timeout)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": "ok", "http_status": int(resp.status)}
    except Exception as exc:
        return {"status": "degraded", "detail": redact_secrets(str(exc))[:160]}


def run_deep_health_check(
    *,
    agents_enabled: bool,
    code_mode_enabled: bool,
    mcp_base_url: str | None = None,
    sandbox_url: str | None = None,
    http_transport: Any | None = None,
    db_probe: Any | None = None,
) -> dict[str, Any]:
    """Checks optional downstream dependencies without ever leaking secrets or DSNs."""
    checks: dict[str, Any] = {}

    if db_probe is not None:
        try:
            db_probe()
            checks["database"] = {"status": "ok"}
        except Exception as exc:
            checks["database"] = {"status": "degraded", "detail": redact_secrets(str(exc))[:160]}
    else:
        db_configured = bool((os.environ.get("DATABASE_URL") or "").strip())
        checks["database"] = {"status": "ok" if db_configured else "memory_fallback"}

    mcp_target = (mcp_base_url or os.environ.get("MCP_BASE_URL") or "").strip()
    if mcp_target:
        # Derive Knowledge Studio health URL from MCP endpoint
        studio_health = mcp_target.split("/api/v1/mcp")[0].rstrip("/") + "/api/v1/health"
        checks["knowledge_studio_mcp"] = _probe_http(studio_health, transport=http_transport)

    if code_mode_enabled:
        sb_target = (sandbox_url or os.environ.get("CODE_SANDBOX_URL") or "http://code-sandbox-runner:8090").rstrip("/")
        checks["code_sandbox_runner"] = _probe_http(f"{sb_target}/health", transport=http_transport)
    else:
        checks["code_sandbox_runner"] = {"status": "disabled"}

    degraded = any(item.get("status") == "degraded" for item in checks.values())
    return {
        "status": "degraded" if degraded else "ok",
        "agents_enabled": agents_enabled,
        "code_mode_enabled": code_mode_enabled,
        "checks": checks,
    }


def serialize_health(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False)
