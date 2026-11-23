"""Persisted proactive document findings repository with strict DETECTED -> CONFIRMED -> ACTIONED HITL guard (EVO-015)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.database.audit_logger import AuditLogger

VALID_CATEGORIES = frozenset({"expiration", "obligation", "risk", "discrepancy"})
VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


class FindingStateError(RuntimeError):
    """Raised when an invalid HITL transition is attempted (e.g. promoting an unconfirmed finding)."""


def verify_provenance_quote(quote: str, chunk_text: str | None = None) -> str:
    cleaned = (quote or "").strip()
    if len(cleaned) < 3:
        raise ValueError("Finding requires a verifiable provenance_quote of at least 3 characters.")
    if chunk_text is not None and cleaned.lower() not in chunk_text.lower():
        raise ValueError("Finding provenance_quote does not appear in the referenced document chunk.")
    return cleaned[:600]


class InMemoryFindingsRepository:
    def __init__(self, audit_logger: AuditLogger | None = None) -> None:
        self._findings: dict[str, dict[str, Any]] = {}
        self._audit = audit_logger

    def record_finding(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        document_id: str,
        category: str,
        severity: str,
        title: str,
        summary: str,
        provenance_quote: str,
        provenance_chunk_index: int = 0,
        chunk_text: str | None = None,
        run_id: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported finding category: {category}")
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported finding severity: {severity}")
        verified_quote = verify_provenance_quote(provenance_quote, chunk_text)
        finding_id = f"fnd_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        rec: dict[str, Any] = {
            "finding_id": finding_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "document_id": document_id,
            "category": category,
            "severity": severity,
            "title": title.strip()[:200],
            "summary": summary.strip()[:1000],
            "due_date": due_date,
            "provenance_quote": verified_quote,
            "provenance_chunk_index": max(0, int(provenance_chunk_index)),
            "status": "DETECTED",
            "reviewed_by_user_id": None,
            "reviewed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self._findings[finding_id] = rec
        if self._audit is not None:
            self._audit.record(
                event_type="agent.finding.detected",
                tenant_id=tenant_id,
                actor_user_id=owner_user_id,
                run_id=run_id or finding_id,
                metadata={"finding_id": finding_id, "category": category, "severity": severity},
            )
        return deepcopy(rec)

    def list_findings(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            deepcopy(f)
            for f in self._findings.values()
            if f["tenant_id"] == tenant_id
            and f["owner_user_id"] == owner_user_id
            and (status is None or f["status"] == status)
        ]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return rows

    def review_finding(
        self,
        *,
        finding_id: str,
        tenant_id: str,
        reviewer_user_id: str,
        decision: str,
    ) -> dict[str, Any]:
        rec = self._findings.get(finding_id)
        if not rec or rec["tenant_id"] != tenant_id:
            raise KeyError("Finding not found.")
        if rec["status"] != "DETECTED":
            raise FindingStateError(f"Finding '{finding_id}' is already in state {rec['status']}.")
        normalized = decision.strip().lower()
        if normalized == "confirm":
            new_status = "CONFIRMED"
        elif normalized == "dismiss":
            new_status = "DISMISSED"
        else:
            raise ValueError("Decision must be 'confirm' or 'dismiss'.")
        now = datetime.now(timezone.utc).isoformat()
        rec["status"] = new_status
        rec["reviewed_by_user_id"] = reviewer_user_id
        rec["reviewed_at"] = now
        rec["updated_at"] = now
        if self._audit is not None:
            self._audit.record(
                event_type=f"agent.finding.{new_status.lower()}",
                tenant_id=tenant_id,
                actor_user_id=reviewer_user_id,
                run_id=rec.get("run_id") or finding_id,
                metadata={"finding_id": finding_id, "status": new_status},
            )
        return deepcopy(rec)

    def mark_actioned(
        self,
        *,
        finding_id: str,
        tenant_id: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        rec = self._findings.get(finding_id)
        if not rec or rec["tenant_id"] != tenant_id:
            raise KeyError("Finding not found.")
        if rec["status"] != "CONFIRMED":
            raise FindingStateError(
                f"Cannot promote finding '{finding_id}' from state {rec['status']}; human confirmation (CONFIRMED) is mandatory."
            )
        now = datetime.now(timezone.utc).isoformat()
        rec["status"] = "ACTIONED"
        rec["updated_at"] = now
        if self._audit is not None:
            self._audit.record(
                event_type="agent.finding.actioned",
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                run_id=rec.get("run_id") or finding_id,
                metadata={"finding_id": finding_id, "status": "ACTIONED"},
            )
        return deepcopy(rec)


class PostgresFindingsRepository:
    """PostgreSQL implementation over agents.agent_findings enforcing strict HITL transitions."""

    def __init__(self, session: Session, audit_logger: AuditLogger | None = None) -> None:
        self._session = session
        self._audit = audit_logger

    def record_finding(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        document_id: str,
        category: str,
        severity: str,
        title: str,
        summary: str,
        provenance_quote: str,
        provenance_chunk_index: int = 0,
        chunk_text: str | None = None,
        run_id: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported finding category: {category}")
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported finding severity: {severity}")
        verified_quote = verify_provenance_quote(provenance_quote, chunk_text)
        finding_id = f"fnd_{uuid.uuid4().hex[:12]}"
        self._session.execute(
            text(
                """
                INSERT INTO agents.agent_findings (
                    finding_id, run_id, tenant_id, owner_user_id, document_id,
                    category, severity, title, summary, due_date,
                    provenance_quote, provenance_chunk_index, status
                ) VALUES (
                    :finding_id, :run_id, :tenant_id, :owner_user_id, :document_id,
                    :category, :severity, :title, :summary, :due_date,
                    :provenance_quote, :provenance_chunk_index, 'DETECTED'
                )
                """
            ),
            {
                "finding_id": finding_id,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "document_id": document_id,
                "category": category,
                "severity": severity,
                "title": title.strip()[:200],
                "summary": summary.strip()[:1000],
                "due_date": due_date,
                "provenance_quote": verified_quote,
                "provenance_chunk_index": max(0, int(provenance_chunk_index)),
            },
        )
        self._session.commit()
        if self._audit is not None:
            self._audit.record(
                event_type="agent.finding.detected",
                tenant_id=tenant_id,
                actor_user_id=owner_user_id,
                run_id=run_id or finding_id,
                metadata={"finding_id": finding_id, "category": category, "severity": severity},
            )
        return {
            "finding_id": finding_id,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "category": category,
            "severity": severity,
            "title": title.strip()[:200],
            "provenance_quote": verified_quote,
            "status": "DETECTED",
        }
