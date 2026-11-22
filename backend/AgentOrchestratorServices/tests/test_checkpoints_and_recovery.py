from __future__ import annotations

import pytest
from app.application.graph.research_graph import ResearchAgentGraph
from app.application.quota_service import TenantQuotaService
from app.application.tools.registry import ToolRegistry
from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.checkpointer import (
    InMemoryCheckpointer,
    UnsafeSerializationError,
    compact_checkpoint_state,
)
from app.infrastructure.database.runs_repository import InMemoryRunsRepository
from app.infrastructure.llm.model_factory import (
    ResolvedLLMConfig,
    build_agent_model_client,
)


class _UnsafeObject:
    pass


def test_strict_msgpack_rejects_arbitrary_python_objects_and_compacts_evidence() -> None:
    with pytest.raises(UnsafeSerializationError):
        compact_checkpoint_state({"bad": _UnsafeObject()})

    compact = compact_checkpoint_state(
        {
            "goal": "Analizar Bearer secret.token.123",
            "evidence": [
                {"document_id": "doc-1", "chunk_index": 0, "filename": "a.pdf", "quote": "x" * 2000}
            ],
        }
    )
    assert "[REDACTED]" in compact["goal"]
    assert len(compact["evidence"][0]["quote"]) == 400


def test_checkpoint_restart_recovery_and_cross_tenant_isolation() -> None:
    repo = InMemoryRunsRepository()
    checkpointer = InMemoryCheckpointer()
    audit = AuditLogger()
    quota = TenantQuotaService()

    cfg = ResolvedLLMConfig(
        provider="ollama",
        api_key="ollama-local",
        model="qwen2.5:3b",
        base_url="http://127.0.0.1:11434/v1",
        allow_local=True,
        source="database",
    )

    def llm_transport(_url, _payload, _headers, _timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"action":"request_approval","approval_action":"save_studio_artifact","summary":"Guardar informe","content":"Informe preliminar verificado."}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    graph_before_restart = ResearchAgentGraph(
        registry=ToolRegistry(),
        model_client=build_agent_model_client(cfg, transport=llm_transport),
        repo=repo,
        checkpointer=checkpointer,
        quota_service=quota,
        audit_logger=audit,
    )

    owner = {"user_id": "user-1", "active_tenant_id": "tenant-A", "raw_token": "jwt-a"}
    run = graph_before_restart.start_run(
        user=owner,
        goal="Preparar informe ejecutivo",
        idempotency_key="idem-restart-01",
    )
    assert run["status"] == "WAITING_APPROVAL"
    approval_id = run["pending_approval"]["approval_id"]

    # Cross-tenant / cross-user isolation: another tenant or user gets None (HTTP 404)
    assert repo.get_run(run["run_id"], tenant_id="tenant-B", owner_user_id="user-1") is None
    assert repo.get_run(run["run_id"], tenant_id="tenant-A", owner_user_id="user-2") is None
    assert checkpointer.load_latest(thread_id=run["thread_id"], tenant_id="tenant-B", owner_user_id="user-1") is None

    # Simulate container restart by creating a brand new ResearchAgentGraph instance sharing persisted repo/checkpointer
    graph_after_restart = ResearchAgentGraph(
        registry=ToolRegistry(),
        model_client=build_agent_model_client(cfg, transport=llm_transport),
        repo=repo,
        checkpointer=checkpointer,
        quota_service=quota,
        audit_logger=audit,
    )
    resumed = graph_after_restart.resume_from_checkpoint(
        run_id=run["run_id"],
        approval_id=approval_id,
        decision="approve",
        comment="Aprobado tras reinicio",
        user=owner,
    )
    assert resumed["status"] == "SUCCEEDED"
    assert resumed["current_step"] == "completed_approved"
