from __future__ import annotations

import pytest
from app.application.graph.research_graph import ResearchAgentGraph
from app.application.quota_service import QuotaExceededError, TenantQuotaService
from app.application.tools.registry import ToolRegistry
from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.checkpointer import InMemoryCheckpointer
from app.infrastructure.database.runs_repository import (
    ApprovalConflictError,
    InMemoryRunsRepository,
)
from app.infrastructure.llm.model_factory import (
    ResolvedLLMConfig,
    build_agent_model_client,
)


def _cfg() -> ResolvedLLMConfig:
    return ResolvedLLMConfig(
        provider="ollama",
        api_key="ollama-local",
        model="qwen2.5:3b",
        base_url="http://127.0.0.1:11434/v1",
        allow_local=True,
        source="database",
    )


def test_hitl_reject_and_double_resume_conflict_and_audit() -> None:
    repo = InMemoryRunsRepository()
    audit = AuditLogger()
    graph = ResearchAgentGraph(
        registry=ToolRegistry(),
        model_client=build_agent_model_client(
            _cfg(),
            transport=lambda *_a: {
                "choices": [{"message": {"content": "Informe listo"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30},
            },
        ),
        repo=repo,
        checkpointer=InMemoryCheckpointer(),
        quota_service=TenantQuotaService(),
        audit_logger=audit,
    )
    user = {"user_id": "u-1", "active_tenant_id": "t-1", "raw_token": "jwt-1"}
    run = graph.start_run(user=user, goal="Guardar en Studio", save_to_studio=True, idempotency_key="hitl-1")
    assert run["status"] == "WAITING_APPROVAL"
    approval_id = run["pending_approval"]["approval_id"]

    # Reject decision completes without writing
    rejected = graph.resume_from_checkpoint(
        run_id=run["run_id"],
        approval_id=approval_id,
        decision="reject",
        comment="Falta revisar cláusula 4",
        user=user,
    )
    assert rejected["status"] == "SUCCEEDED"
    assert rejected["studio_handoff"]["status"] == "rejected_by_human"

    # Double resume raises ApprovalConflictError (HTTP 409)
    with pytest.raises(ApprovalConflictError):
        graph.resume_from_checkpoint(
            run_id=run["run_id"],
            approval_id=approval_id,
            decision="approve",
            comment="Segundo intento",
            user=user,
        )

    event_types = [ev["event_type"] for ev in audit.events]
    assert "agent.run.started" in event_types
    assert "agent.approval.requested" in event_types
    assert "agent.approval.decided" in event_types


def test_cooperative_cancellation_and_daily_quota_429() -> None:
    repo = InMemoryRunsRepository()
    quota = TenantQuotaService(daily_token_quota=1000, daily_run_quota=2)

    # Consume quota to trigger QuotaExceededError (mapped to HTTP 429)
    quota.consume("t-quota", runs_delta=2, tokens_delta=900)
    with pytest.raises(QuotaExceededError):
        quota.check_can_start("t-quota", requested_max_tokens=500)

    # Cooperative cancellation
    run = repo.create_run(
        tenant_id="t-quota",
        owner_user_id="u-1",
        idempotency_key="cancel-1",
        mode="agent",
        goal="Investigación larga",
        document_ids=[],
    )
    cancelled = repo.request_cancel(run["run_id"], tenant_id="t-quota", owner_user_id="u-1")
    assert cancelled is not None
    assert cancelled["status"] == "CANCELLED"
    assert repo.is_cancel_requested(run["run_id"]) is True
