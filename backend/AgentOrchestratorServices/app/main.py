"""FastAPI entrypoint for optional AgentOrchestratorServices (AG-004 / AG-005), gated by AGENTS_ENABLED."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.application.tools.registry import ToolRegistry
from app.config.security import require_agent_user
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools


def is_agents_enabled() -> bool:
    return os.environ.get("AGENTS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def is_code_mode_enabled() -> bool:
    return os.environ.get("CODE_MODE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _require_agents_enabled() -> None:
    if not is_agents_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AgentOrchestratorServices está deshabilitado (AGENTS_ENABLED=false).",
        )


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    mcp_url = os.environ.get("MCP_BASE_URL", "http://knowledge-studio-service:8000/api/v1/mcp")
    register_default_mcp_tools(registry, McpHttpClient(mcp_url))
    return registry


app = FastAPI(title="Blandskron Agent Orchestrator API", version="1.0.0")
_cors_raw = os.environ.get("CORS_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]')
try:
    _cors_origins = json.loads(_cors_raw) if isinstance(_cors_raw, str) else ["http://localhost:3000"]
except ValueError:
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "agents_enabled": is_agents_enabled(),
        "code_mode_enabled": is_code_mode_enabled(),
    }


@app.get("/api/v1/agents/tools")
def list_tools(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    _require_agents_enabled()
    registry = build_default_registry()
    return {"tenant_id": user["active_tenant_id"], "tools": registry.list_specs()}
