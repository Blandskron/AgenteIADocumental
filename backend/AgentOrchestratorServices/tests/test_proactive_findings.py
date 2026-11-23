"""Tests for EVO-015: persisted proactive findings, provenance verification, and strict HITL transitions."""

from __future__ import annotations

import pytest

from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.findings_repository import FindingStateError, InMemoryFindingsRepository


def test_finding_enforces_provenance_and_strict_detected_confirmed_actioned_flow() -> None:
    audit = AuditLogger()
    repo = InMemoryFindingsRepository(audit_logger=audit)

    # Unanchored quote must be rejected
    with pytest.raises(ValueError, match="does not appear"):
        repo.record_finding(
            tenant_id="tenant-1",
            owner_user_id="user-1",
            document_id="doc-1",
            category="expiration",
            severity="high",
            title="Vencimiento",
            summary="Vence pronto",
            provenance_quote="cita inventada",
            chunk_text="El contrato vence el 30 de noviembre de 2026.",
        )

    finding = repo.record_finding(
        tenant_id="tenant-1",
        owner_user_id="user-1",
        document_id="doc-1",
        category="expiration",
        severity="high",
        title="Vencimiento de contrato",
        summary="Renovacion requerida antes del 30/11/2026.",
        due_date="2026-11-30",
        provenance_quote="vence el 30 de noviembre de 2026",
        chunk_text="El contrato vence el 30 de noviembre de 2026.",
    )
    assert finding["status"] == "DETECTED"

    # Promoting directly from DETECTED without human confirmation MUST fail
    with pytest.raises(FindingStateError):
        repo.mark_actioned(finding_id=finding["finding_id"], tenant_id="tenant-1", actor_user_id="user-1")

    confirmed = repo.review_finding(
        finding_id=finding["finding_id"],
        tenant_id="tenant-1",
        reviewer_user_id="user-1",
        decision="confirm",
    )
    assert confirmed["status"] == "CONFIRMED"

    actioned = repo.mark_actioned(finding_id=finding["finding_id"], tenant_id="tenant-1", actor_user_id="user-1")
    assert actioned["status"] == "ACTIONED"

    event_types = [ev["event_type"] for ev in audit.events]
    assert event_types == ["agent.finding.detected", "agent.finding.confirmed", "agent.finding.actioned"]
