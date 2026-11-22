"""FastAPI entrypoint for optional AgentOrchestratorServices (AG-004 / AG-005), gated by AGENTS_ENABLED."""

from __future__ import annotations

import json
import os
from typing import Any

from app.application.graph.code_mode_node import (
    describe_readonly_tool,
    discover_readonly_tools,
)
from app.application.health_service import run_deep_health_check
from app.application.tools.registry import ToolRegistry
from app.config.security import require_agent_user
from app.infrastructure.access.access_client import (
    DocumentAccessHttpClient,
    register_document_access_tools,
)
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools
from app.infrastructure.search.search_client import (
    DocumentSearchHttpClient,
    register_document_search_tools,
)
from app.interfaces.api.v1.runs_routes import router as runs_router
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware


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
    search_url = os.environ.get("DOCUMENT_SEARCH_BASE_URL", "http://document-search-service:8000")
    register_document_search_tools(registry, DocumentSearchHttpClient(search_url))
    access_url = os.environ.get("DOCUMENT_ACCESS_BASE_URL", "http://document-access-service:8000")
    register_document_access_tools(registry, DocumentAccessHttpClient(access_url))
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
app.include_router(runs_router)


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "agents_enabled": is_agents_enabled(),
        "code_mode_enabled": is_code_mode_enabled(),
    }


@app.get("/api/v1/health/deep")
def deep_health(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    report = run_deep_health_check(
        agents_enabled=is_agents_enabled(),
        code_mode_enabled=is_code_mode_enabled(),
    )
    report["checked_by_tenant"] = user["active_tenant_id"]
    return report


@app.get("/api/v1/agents/tools")
def list_tools(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    _require_agents_enabled()
    registry = build_default_registry()
    return {"tenant_id": user["active_tenant_id"], "tools": registry.list_specs()}


@app.get("/api/v1/agents/tools/search")
def search_tools(
    q: str = "",
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    registry = build_default_registry()
    return {
        "tenant_id": user["active_tenant_id"],
        "query": q,
        "tools": discover_readonly_tools(registry, q),
    }


@app.get("/api/v1/agents/tools/{tool_name}")
def describe_tool(
    tool_name: str,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    registry = build_default_registry()
    spec = describe_readonly_tool(registry, tool_name)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Herramienta '{tool_name}' no encontrada en la lista autorizada.",
        )
    return {"tenant_id": user["active_tenant_id"], "tool": spec}

