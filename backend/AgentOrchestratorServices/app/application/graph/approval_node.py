"""Human-in-the-Loop approval node mirroring LangGraph interrupt() / Command(resume=...) (AG-009)."""

from __future__ import annotations

from typing import Any

from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.runs_repository import (
    InMemoryRunsRepository,
    PostgresRunsRepository,
)
from app.infrastructure.studio.studio_client import StudioHandoffClient


def request_human_approval(
    *,
    repo: InMemoryRunsRepository | PostgresRunsRepository,
    audit_logger: AuditLogger,
    run_id: str,
    tenant_id: str,
    owner_user_id: str,
    action: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Freezes the run in WAITING_APPROVAL and persists an explicit approval request."""
    approval = repo.create_approval(
        run_id=run_id,
        tenant_id=tenant_id,
        requested_by_user_id=owner_user_id,
        action=action,
        summary=summary,
        payload=payload,
    )
    audit_logger.record(
        event_type="agent.approval.requested",
        tenant_id=tenant_id,
        actor_user_id=owner_user_id,
        run_id=run_id,
        metadata={"approval_id": approval["approval_id"], "action": action},
    )
    return approval


def resume_human_approval(
    *,
    repo: InMemoryRunsRepository | PostgresRunsRepository,
    audit_logger: AuditLogger,
    run_id: str,
    approval_id: str,
    tenant_id: str,
    owner_user_id: str,
    decision: str,
    comment: str = "",
    user_jwt: str = "",
    studio_client: StudioHandoffClient | None = None,
) -> dict[str, Any]:
    """Resumes a WAITING_APPROVAL run after explicit human approve/reject decision."""
    decided = repo.decide_approval(
        run_id=run_id,
        approval_id=approval_id,
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        decision=decision,
        comment=comment,
    )
    audit_logger.record(
        event_type="agent.approval.decided",
        tenant_id=tenant_id,
        actor_user_id=owner_user_id,
        run_id=run_id,
        metadata={
            "approval_id": approval_id,
            "decision": decided["decision"],
            "action": decided["action"],
        },
    )

    run = repo.get_run(run_id, tenant_id=tenant_id, owner_user_id=owner_user_id)
    if run is None:
        raise KeyError("Run not found.")

    if decided["decision"] != "APPROVED":
        return repo.update_run(
            run_id,
            status="SUCCEEDED",
            current_step="completed_without_write",
            pending_approval=None,
            studio_handoff={"status": "rejected_by_human", "comment": comment},
        )

    handoff_result: dict[str, Any] = {"status": "approved", "action": decided["action"]}
    if decided["action"] == "save_studio_artifact" and studio_client is not None:
        sources = run.get("sources") or []
        handoff_result = studio_client.save_approved_artifact(
            user_jwt=user_jwt,
            title=str(run.get("goal") or "Informe Agente")[:120],
            template_id="summary.executive",
            result_markdown=str(run.get("result_markdown") or ""),
            sources=sources,
            evidence=sources,
        )

    return repo.update_run(
        run_id,
        status="SUCCEEDED",
        current_step="completed_approved",
        pending_approval=None,
        studio_handoff=handoff_result,
    )
