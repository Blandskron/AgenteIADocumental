"""HTTP and SSE endpoints for AgentOrchestratorServices runs, HITL resume and cancel (AG-007..AG-012)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from app.application.export_service import export_run_csv, export_run_markdown
from app.application.graph.code_mode_node import (
    CodeModeDisabledError,
    is_code_mode_enabled,
)
from app.application.graph.research_graph import ResearchAgentGraph
from app.application.metrics_service import AgentMetricsCollector
from app.application.quota_service import QuotaExceededError, TenantQuotaService
from app.application.templates.agent_templates import list_agent_templates
from app.application.tools.registry import ToolRegistry
from app.config.security import require_agent_user
from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.checkpointer import (
    InMemoryCheckpointer,
    PostgresAgentCheckpointer,
)
from app.infrastructure.database.runs_repository import (
    ApprovalConflictError,
    InMemoryRunsRepository,
    PostgresRunsRepository,
)
from app.infrastructure.llm.model_factory import (
    LLMConfigurationError,
    LLMProviderError,
    TenantLLMConfigResolver,
    build_agent_model_client,
)
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools
from app.infrastructure.sandbox.sandbox_client import SandboxHttpClient
from app.infrastructure.search.search_client import (
    DocumentSearchHttpClient,
    register_document_search_tools,
)
from app.infrastructure.studio.studio_client import StudioHandoffClient
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Shared runtime stores (overridable in tests or backed by PostgreSQL when DATABASE_URL is configured)
_fallback_repo = InMemoryRunsRepository()
_fallback_checkpointer = InMemoryCheckpointer()
_fallback_quota = TenantQuotaService()
_fallback_audit = AuditLogger()
_metrics_collector = AgentMetricsCollector()


class StartAgentRunRequest(BaseModel):
    mode: str = Field(default="agent", pattern="^(agent|code_mode)$")
    goal: str = Field(min_length=3, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, max_length=25)
    template_id: str | None = Field(default=None, max_length=64)
    enable_code_mode: bool = False
    save_to_studio: bool = False
    max_steps: int = Field(default=8, ge=1, le=15)
    max_tokens: int = Field(default=12000, ge=500, le=32000)
    idempotency_key: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}", min_length=3, max_length=128)


class ResumeApprovalRequest(BaseModel):
    approval_id: str = Field(min_length=3, max_length=64)
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = Field(default="", max_length=500)


def _require_agents_enabled() -> None:
    enabled = os.environ.get("AGENTS_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AgentOrchestratorServices está deshabilitado (AGENTS_ENABLED=false).",
        )


def _get_runtime_components():
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if db_url:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session

        engine = create_engine(db_url, pool_pre_ping=True)
        session = Session(engine)

        def _load_integration(tenant_id: str, provider: str) -> dict[str, Any] | None:
            row = session.execute(
                text(
                    """
                    SELECT status, config, secrets_encrypted, updated_at
                    FROM public.tenant_integrations
                    WHERE tenant_id = :tenant_id AND provider = :provider
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "provider": provider},
            ).mappings().first()
            return dict(row) if row else None

        return (
            PostgresRunsRepository(session),
            PostgresAgentCheckpointer(session),
            TenantQuotaService(session=session),
            AuditLogger(session=session),
            TenantLLMConfigResolver(row_loader=_load_integration),
        )
    return (
        _fallback_repo,
        _fallback_checkpointer,
        _fallback_quota,
        _fallback_audit,
        TenantLLMConfigResolver(),
    )


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    mcp_url = os.environ.get("MCP_BASE_URL", "http://knowledge-studio-service:8000/api/v1/mcp")
    register_default_mcp_tools(registry, McpHttpClient(mcp_url))
    search_url = os.environ.get("DOCUMENT_SEARCH_BASE_URL", "http://document-search-service:8000")
    register_document_search_tools(registry, DocumentSearchHttpClient(search_url))
    return registry


def _build_sandbox() -> SandboxHttpClient:
    sandbox_url = os.environ.get("CODE_SANDBOX_URL", "http://code-sandbox-runner:8090")
    timeout_ms = int(os.environ.get("CODE_SANDBOX_TIMEOUT_MS", "5000"))
    return SandboxHttpClient(sandbox_url, timeout_ms=timeout_ms)


def _build_studio() -> StudioHandoffClient:
    studio_url = os.environ.get("KNOWLEDGE_STUDIO_BASE_URL", "http://knowledge-studio-service:8000")
    export_url = os.environ.get("DOCUMENT_EXPORT_BASE_URL", "http://document-export-service:8000")
    return StudioHandoffClient(studio_url, export_base_url=export_url)


@router.post("/runs", status_code=status.HTTP_201_CREATED)
def create_agent_run(
    payload: StartAgentRunRequest,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    if (payload.enable_code_mode or payload.mode == "code_mode") and not is_code_mode_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "CODE_MODE_DISABLED", "message": "Code Mode está deshabilitado (CODE_MODE_ENABLED=false)."},
        )

    repo, checkpointer, quota, audit, llm_resolver = _get_runtime_components()
    try:
        llm_cfg = llm_resolver.resolve(str(user["active_tenant_id"]))
        model_client = build_agent_model_client(llm_cfg)
        graph = ResearchAgentGraph(
            registry=_build_registry(),
            model_client=model_client,
            repo=repo,
            checkpointer=checkpointer,
            quota_service=quota,
            audit_logger=audit,
            sandbox_client=_build_sandbox(),
            studio_client=_build_studio(),
        )
        run = graph.start_run(
            user=user,
            goal=payload.goal,
            document_ids=payload.document_ids,
            mode=payload.mode,
            enable_code_mode=payload.enable_code_mode or payload.mode == "code_mode",
            max_steps=payload.max_steps,
            max_tokens=payload.max_tokens,
            idempotency_key=payload.idempotency_key,
            save_to_studio=payload.save_to_studio,
            template_id=payload.template_id,
        )
        _metrics_collector.record_run_outcome(
            tenant_id=str(user["active_tenant_id"]),
            status=str(run.get("status") or "UNKNOWN"),
            provider=run.get("provider"),
            steps_used=int(run.get("steps_used") or 0),
            usage_tokens=int(run.get("usage_tokens") or 0),
            code_mode_used=bool(run.get("code_executions")),
        )
        return run
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except CodeModeDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from None
    except QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from None
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from None
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": str(exc)},
        ) from None


@router.get("/runs")
def list_agent_runs(
    limit: int = 20,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    repo, *_ = _get_runtime_components()
    items = repo.list_runs(
        tenant_id=str(user["active_tenant_id"]),
        owner_user_id=str(user["user_id"]),
        limit=limit,
    )
    return {"items": items}


@router.get("/runs/{run_id}")
def get_agent_run(
    run_id: str,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    repo, *_ = _get_runtime_components()
    run = repo.get_run(
        run_id,
        tenant_id=str(user["active_tenant_id"]),
        owner_user_id=str(user["user_id"]),
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución de agente no encontrada.")
    return run


@router.get("/runs/{run_id}/stream")
def stream_agent_run(
    run_id: str,
    user: dict[str, Any] = Depends(require_agent_user),
) -> StreamingResponse:
    _require_agents_enabled()
    repo, *_ = _get_runtime_components()
    run = repo.get_run(
        run_id,
        tenant_id=str(user["active_tenant_id"]),
        owner_user_id=str(user["user_id"]),
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución de agente no encontrada.")

    def _event_generator():
        for step in run.get("steps") or []:
            yield f"event: step\ndata: {json.dumps(step, ensure_ascii=False)}\n\n"
        if run.get("pending_approval"):
            yield f"event: approval\ndata: {json.dumps(run['pending_approval'], ensure_ascii=False)}\n\n"
        yield f"event: status\ndata: {json.dumps(run, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@router.post("/runs/{run_id}/resume")
def resume_agent_run(
    run_id: str,
    payload: ResumeApprovalRequest,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    repo, _, _, audit, _ = _get_runtime_components()
    try:
        from app.application.graph.approval_node import resume_human_approval

        run = repo.get_run(
            run_id,
            tenant_id=str(user["active_tenant_id"]),
            owner_user_id=str(user["user_id"]),
        )
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución de agente no encontrada.")
        return resume_human_approval(
            repo=repo,
            audit_logger=audit,
            run_id=run_id,
            approval_id=payload.approval_id,
            tenant_id=str(user["active_tenant_id"]),
            owner_user_id=str(user["user_id"]),
            decision=payload.decision,
            comment=payload.comment,
            user_jwt=str(user.get("raw_token") or ""),
            studio_client=_build_studio(),
        )
    except ApprovalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aprobación o ejecución no encontrada.") from None


@router.post("/runs/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    user: dict[str, Any] = Depends(require_agent_user),
) -> dict[str, Any]:
    _require_agents_enabled()
    repo, _, _, audit, _ = _get_runtime_components()
    updated = repo.request_cancel(
        run_id,
        tenant_id=str(user["active_tenant_id"]),
        owner_user_id=str(user["user_id"]),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución de agente no encontrada.")
    audit.record(
        event_type="agent.run.cancelled",
        tenant_id=str(user["active_tenant_id"]),
        actor_user_id=str(user["user_id"]),
        run_id=run_id,
        metadata={"status": updated["status"]},
    )
    return updated


@router.get("/templates")
def get_templates(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    _require_agents_enabled()
    return {"tenant_id": user["active_tenant_id"], "templates": list_agent_templates()}


@router.get("/quota")
def get_tenant_quota(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    _require_agents_enabled()
    _, _, quota, _, _ = _get_runtime_components()
    tenant_id = str(user["active_tenant_id"])
    usage = quota.get_usage(tenant_id)
    return {
        "tenant_id": tenant_id,
        "runs_used": usage["runs_count"],
        "runs_limit": int(os.environ.get("AGENT_DAILY_RUN_QUOTA", "200")),
        "tokens_used": usage["tokens_used"],
        "tokens_limit": int(os.environ.get("AGENT_DAILY_TOKEN_QUOTA", "200000")),
    }


@router.get("/metrics")
def get_tenant_metrics(user: dict[str, Any] = Depends(require_agent_user)) -> dict[str, Any]:
    _require_agents_enabled()
    return _metrics_collector.snapshot(str(user["active_tenant_id"]))


@router.get("/runs/{run_id}/export")
def export_agent_run(
    run_id: str,
    format: str = "markdown",
    user: dict[str, Any] = Depends(require_agent_user),
) -> PlainTextResponse:
    _require_agents_enabled()
    repo, *_ = _get_runtime_components()
    run = repo.get_run(
        run_id,
        tenant_id=str(user["active_tenant_id"]),
        owner_user_id=str(user["user_id"]),
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución de agente no encontrada.")
    fmt = (format or "markdown").strip().lower()
    if fmt == "csv":
        return PlainTextResponse(
            content=export_run_csv(run),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'},
        )
    if fmt == "markdown":
        return PlainTextResponse(
            content=export_run_markdown(run),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.md"'},
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato no soportado (usa markdown o csv).")
