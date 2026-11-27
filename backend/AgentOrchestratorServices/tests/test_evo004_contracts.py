"""Contract tests for EVO-004: AuditLogger SQL, PostgresRunsRepository JSONB columns, Studio handoff, PDF export, and goal sanitization."""

from __future__ import annotations

import uuid
from typing import Any

from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.runs_repository import PostgresRunsRepository
from app.infrastructure.export.pdf_export_client import AgentPdfExportClient
from app.infrastructure.studio.studio_client import StudioHandoffClient


class _FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _RecordingSession:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        sql = str(statement)
        self.queries.append((sql, dict(params or {})))
        if "FROM public.audit_logs" in sql:
            return _FakeResult(
                [
                    {
                        "audit_id": "aud-1",
                        "action": "agent.run.started",
                        "actor_user_id": "u-1",
                        "metadata": {"run_id": "run_1"},
                        "created_at": "2026-11-23T00:00:00Z",
                    }
                ]
            )
        if "SELECT * FROM agents.agent_runs" in sql:
            return _FakeResult([{"run_id": "run_1", "status": "WAITING_APPROVAL"}])
        return _FakeResult()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def test_audit_logger_uses_real_public_audit_logs_columns() -> None:
    session = _RecordingSession()
    logger = AuditLogger(session=session)  # type: ignore[arg-type]

    logger.record(
        event_type="agent.run.started",
        tenant_id="tenant-1",
        actor_user_id="user-1",
        run_id="run_1",
        metadata={"mode": "agent"},
    )
    rows = logger.list_for_run(run_id="run_1", tenant_id="tenant-1")

    assert len(rows) == 1
    assert rows[0]["audit_id"] == "aud-1"
    insert_sql = session.queries[0][0]
    select_sql = session.queries[1][0]
    assert "audit_id" in insert_sql and "resource_type" in insert_sql and "resource_id" in insert_sql
    assert "target_type" not in insert_sql and "target_id" not in insert_sql
    assert "audit_id" in select_sql and "resource_type = 'agent_run'" in select_sql and "resource_id = :run_id" in select_sql


def test_postgres_runs_repository_persists_hitl_and_code_mode_columns() -> None:
    session = _RecordingSession()
    repo = PostgresRunsRepository(session)  # type: ignore[arg-type]

    repo.update_run(
        "run_1",
        status="WAITING_APPROVAL",
        pending_approval={"approval_id": "apr_1", "action": "save_studio_artifact"},
        code_executions=[{"exit_code": 0}],
        studio_handoff={"status": "saved", "artifact_id": "art-1"},
    )

    update_sql, params = session.queries[0]
    assert "pending_approval = CAST(:pending_approval AS jsonb)" in update_sql
    assert "code_executions = CAST(:code_executions AS jsonb)" in update_sql
    assert "studio_handoff = CAST(:studio_handoff AS jsonb)" in update_sql
    assert "apr_1" in params["pending_approval"]


def test_studio_handoff_sends_valid_p0_template_and_artifact_content_schema() -> None:
    captured: dict[str, Any] = {}

    def _transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        return {"artifact_id": "art-123", "status": "FRESH"}

    client = StudioHandoffClient("http://knowledge-studio-service:8000", transport=_transport)
    result = client.save_approved_artifact(
        user_jwt="jwt-token",
        title="Informe Contrato",
        template_id="executive_brief",
        result_markdown="Plazo de 45 dias [Fuente 1].",
        sources=[{"document_id": "doc-1", "chunk_index": 0, "quote": "Plazo de 45 dias"}],
        evidence=[{"document_id": "doc-1", "chunk_index": 0}],
    )

    assert result["status"] == "saved"
    assert captured["payload"]["template_id"] == "summary.executive"
    content = captured["payload"]["content"]
    assert content["template_id"] == "summary.executive"
    assert content["body_md"] == "Plazo de 45 dias [Fuente 1]."
    assert content["claims"][0]["statement"] == "Plazo de 45 dias"
    assert content["claims"][0]["citations"][0]["quote_text"] == "Plazo de 45 dias"


def test_pdf_export_client_uses_chat_message_pdf_route_and_uuid_idempotency() -> None:
    captured: dict[str, Any] = {}

    def _transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"export_id": "exp-99"}

    client = AgentPdfExportClient("http://document-export-service:8000", transport=_transport)
    res = client.export_run_to_pdf(
        run={
            "run_id": "run_abc123",
            "goal": "Revisar clausulas",
            "result_markdown": "Se detectaron 2 clausulas clave.",
            "sources": [{"document_id": "doc-1", "filename": "a.pdf", "quote": "Clausula 1", "extra_field": "ignored"}],
            "steps_used": 2,
        },
        user_jwt="jwt-token",
    )

    assert res["status"] == "created"
    assert captured["url"] == "http://document-export-service:8000/api/v1/exports/chat-message/pdf"
    parsed_uuid = uuid.UUID(captured["headers"]["Idempotency-Key"])
    assert parsed_uuid.version == 5
    assert "extra_field" not in captured["payload"]["sources"][0]
    assert captured["payload"]["sources"][0]["snippet"] == "Clausula 1"
