from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    AuditLogModel,
    DocumentAssignmentEventModel,
    DocumentAssignmentModel,
    NotificationModel,
)
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.shared.errors import ConflictError


def counts(workflow):
    with Session(workflow.engine) as session:
        return (
            session.scalar(select(func.count()).select_from(DocumentAssignmentModel).where(
                DocumentAssignmentModel.document_id.in_(workflow.documents.values()),
            )),
            session.scalar(select(func.count()).select_from(DocumentAssignmentEventModel).join(
                DocumentAssignmentModel, DocumentAssignmentEventModel.assignment_id == DocumentAssignmentModel.assignment_id,
            ).where(DocumentAssignmentModel.document_id.in_(workflow.documents.values()))),
            session.scalar(select(func.count()).select_from(NotificationModel).where(
                NotificationModel.recipient_user_id.in_(workflow.users.values()),
            )),
            session.scalar(select(func.count()).select_from(AuditLogModel).where(
                AuditLogModel.actor_user_id.in_(workflow.users.values()),
            )),
        )


def change(workflow, statement, **parameters):
    with workflow.engine.begin() as connection:
        connection.execute(text(statement), parameters)


def test_assignment_uses_document_tenant_and_current_database_role(workflow):
    response = workflow.post(f"{workflow.documents['owned']}/assignments", payload={
        "assigned_to_user_id": workflow.users["recipient"],
    }, active_tenant_id=workflow.foreign_tenant, active_role="USER")
    assert response.status_code == 200
    assert response.json()["tenant_id"] == workflow.tenant
    assert response.json()["assigned_by_role"] == "TENANT_ADMIN"
    assert counts(workflow) == (1, 1, 1, 1)
    with Session(workflow.engine) as session:
        for model in (NotificationModel, AuditLogModel):
            assert session.scalars(select(model).where(model.actor_user_id == workflow.users["manager"])).one().tenant_id == workflow.tenant


def test_identical_assignment_retry_has_no_duplicate_effects(workflow):
    fields = {"due_at": "2030-01-02T10:30:00", "metadata": {"purpose": "synthetic"}, "allow_download": False}
    first, second = workflow.assign(**fields), workflow.assign(**fields)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("actor,document,allowed", [
    ("manager", "owned", True), ("leader", "owned", True), ("leader", "private", False),
    ("outsider", "owned", False), ("other", "owned", False), ("super", "owned", True),
])
def test_assignment_authority_is_scoped_to_document(workflow, actor, document, allowed):
    response = workflow.post(f"{workflow.documents[document]}/assignments", actor, {
        "assigned_to_user_id": workflow.users["recipient"],
    }, active_role="TENANT_ADMIN", is_superadmin=actor != "super", tenant_id=workflow.tenant)
    assert response.status_code == (200 if allowed else 404)
    assert counts(workflow) == ((1, 1, 1, 1) if allowed else (0, 0, 0, 0))


@pytest.mark.parametrize("entity", ["actor", "membership", "role", "tenant"])
def test_stale_actor_authority_cannot_assign(workflow, entity):
    if entity == "actor":
        change(workflow, "UPDATE auth_user SET is_active = false WHERE id = :id", id=int(workflow.users["manager"]))
    elif entity == "tenant":
        change(workflow, "UPDATE tenants SET status = 'SUSPENDED' WHERE tenant_id = :id", id=workflow.tenant)
    else:
        field, value = ("status", "DISABLED") if entity == "membership" else ("role", "USER")
        change(workflow, f"UPDATE tenant_memberships SET {field} = :value WHERE user_id = :id", value=value, id=workflow.users["manager"])
    assert workflow.assign().status_code == 404
    assert counts(workflow) == (0, 0, 0, 0)


@pytest.mark.parametrize("recipient", ["outsider", "unknown", "inactive", "disabled", "noncanonical"])
def test_recipient_requires_active_account_and_membership(workflow, recipient):
    target = "recipient"
    if recipient == "inactive":
        change(workflow, "UPDATE auth_user SET is_active = false WHERE id = :id", id=int(workflow.users[target]))
    elif recipient == "disabled":
        change(workflow, "UPDATE tenant_memberships SET status = 'DISABLED' WHERE user_id = :id", id=workflow.users[target])
    elif recipient == "noncanonical":
        target = f"0{workflow.users[target]}"
    else:
        target = recipient
    assert workflow.assign(recipient=target).status_code == (422 if recipient in ("unknown", "noncanonical") else 400)
    assert counts(workflow) == (0, 0, 0, 0)


@pytest.mark.parametrize("action,payload", [("accept", None), ("reject", {"reason": "Review"}), ("sign", {"signature_value": "Synthetic"})])
def test_only_recipient_can_review(workflow, action, payload):
    assignment_id = workflow.assign().json()["assignment_id"]
    for actor in ("manager", "other", "super"):
        assert workflow.post(f"assignments/{assignment_id}/{action}", actor, payload).status_code == 404
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("action,payload", [("reject", {"reason": "  "}), ("sign", {"signature_value": ""})])
def test_review_requires_reason_or_signature(workflow, action, payload):
    assignment_id = workflow.assign().json()["assignment_id"]
    assert workflow.post(f"assignments/{assignment_id}/{action}", "recipient", payload).status_code == 400
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("action,payload", [
    ("accept", None), ("reject", {"reason": "Review"}), ("sign", {"signature_value": "Synthetic"}),
])
def test_review_retries_are_idempotent_and_terminal_states_conflict(workflow, action, payload):
    assignment_id = workflow.assign().json()["assignment_id"]
    path = f"assignments/{assignment_id}/{action}"
    first = workflow.post(path, "recipient", payload)
    assert first.status_code == 200
    assert workflow.post(path, "recipient", payload).json() == first.json()
    if action == "accept":
        assert workflow.post(f"assignments/{assignment_id}/reject", "recipient", {"reason": "Changed"}).status_code == 409
        assert workflow.post(f"assignments/{assignment_id}/sign", "recipient", {"signature_value": "Synthetic"}).status_code == 200
        assert counts(workflow) == (1, 3, 3, 3)
    else:
        changed = {"reason": "Changed"} if action == "reject" else {"signature_value": "Changed"}
        assert workflow.post(path, "recipient", changed).status_code == 409
        assert workflow.post(f"assignments/{assignment_id}/accept", "recipient").status_code == 409
        assert counts(workflow) == (1, 2, 2, 2)


@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED"])
def test_revoked_assignments_cannot_be_revived_by_recipient(workflow, status):
    assignment_id = workflow.assign().json()["assignment_id"]
    change(workflow, "UPDATE document_assignments SET status = :status WHERE assignment_id = :id", status=status, id=assignment_id)
    for action, payload in (("accept", None), ("reject", {"reason": "Review"}), ("sign", {"signature_value": "Synthetic"})):
        assert workflow.post(f"assignments/{assignment_id}/{action}", "recipient", payload).status_code == 409
    assert counts(workflow) == (1, 1, 1, 1)


def test_cancel_signed_assignment_and_reassign_resets_signature(workflow):
    assignment_id = workflow.assign(actor="leader").json()["assignment_id"]
    assert workflow.post(f"assignments/{assignment_id}/sign", "recipient", {"signature_value": "Synthetic"}).status_code == 200
    path = f"assignments/{assignment_id}/cancel"
    cancelled = workflow.post(path, payload={"reason": "Revoke"})
    assert cancelled.status_code == 200
    assert cancelled.json()["signature_value"] == "Synthetic"
    assert workflow.post(path, payload={"reason": "Revoke"}).json() == cancelled.json()
    assert workflow.post(path, payload={"reason": "Changed"}).status_code == 409
    reassigned = workflow.assign().json()
    assert reassigned["assignment_id"] == assignment_id
    assert reassigned["status"] == "PENDING"
    assert reassigned["signature_value"] is reassigned["signed_at"] is reassigned["rejection_reason"] is None
    assert counts(workflow) == (1, 4, 4, 4)
    assert workflow.assign(actor="leader").status_code == 404


@pytest.mark.parametrize("action", ["accept", "cancel"])
def test_disabled_membership_revokes_existing_assignment_actions(workflow, action):
    assignment_id = workflow.assign().json()["assignment_id"]
    actor = "recipient" if action == "accept" else "manager"
    change(workflow, "UPDATE tenant_memberships SET status = 'DISABLED' WHERE user_id = :id", id=workflow.users[actor])
    assert workflow.post(f"assignments/{assignment_id}/{action}", actor).status_code == 404
    assert counts(workflow) == (1, 1, 1, 1)


def test_cancellation_authority_and_expired_conflict(workflow):
    assignment_id = workflow.assign().json()["assignment_id"]
    for actor in ("recipient", "other", "outsider"):
        assert workflow.post(f"assignments/{assignment_id}/cancel", actor).status_code == 404
    change(workflow, "UPDATE document_assignments SET status = 'EXPIRED' WHERE assignment_id = :id", id=assignment_id)
    assert workflow.post(f"assignments/{assignment_id}/cancel").status_code == 409
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("action", ["accept", "reject", "sign"])
def test_viewed_assignment_can_be_reviewed(workflow, action):
    assignment_id = workflow.assign().json()["assignment_id"]
    change(workflow, "UPDATE document_assignments SET status = 'VIEWED' WHERE assignment_id = :id", id=assignment_id)
    assert workflow.post(f"assignments/{assignment_id}/{action}", "recipient", {
        "reason": "Review", "signature_value": "Synthetic",
    }).status_code == 200
    assert counts(workflow) == (1, 2, 2, 2)


def test_historical_assignment_with_wrong_tenant_cannot_be_mutated(workflow):
    assignment_id = workflow.assign().json()["assignment_id"]
    change(workflow, "UPDATE document_assignments SET tenant_id = :tenant WHERE assignment_id = :id", tenant=workflow.foreign_tenant, id=assignment_id)
    assert workflow.assign().status_code == 404
    assert workflow.post(f"assignments/{assignment_id}/accept", "recipient").status_code == 404
    assert workflow.post(f"assignments/{assignment_id}/cancel").status_code == 404
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("helper", ["_record_assignment_event", "_notify_assignment", "_audit"])
def test_creation_failure_rolls_back_all_effects(workflow, monkeypatch, helper):
    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic transaction failure")

    monkeypatch.setattr(DocumentAccessRepositoryPg, helper, fail)
    assert workflow.assign().status_code == 500
    assert counts(workflow) == (0, 0, 0, 0)


@pytest.mark.parametrize("action,helper", [("accept", "_audit"), ("sign", "_notify_assignment_actor"), ("cancel", "_audit")])
def test_transition_failure_preserves_committed_state(workflow, monkeypatch, action, helper):
    assignment_id = workflow.assign().json()["assignment_id"]

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic transaction failure")

    monkeypatch.setattr(DocumentAccessRepositoryPg, helper, fail)
    response = workflow.post(f"assignments/{assignment_id}/{action}", "manager" if action == "cancel" else "recipient", {"signature_value": "Synthetic"})
    assert response.status_code == 500
    assert counts(workflow) == (1, 1, 1, 1)
    with Session(workflow.engine) as session:
        assignment = session.get(DocumentAssignmentModel, assignment_id)
        assert assignment.status == "PENDING"
        assert assignment.signature_value is assignment.signed_at is None


def test_notification_read_is_recipient_only_and_idempotent(workflow):
    workflow.assign()
    with Session(workflow.engine) as session:
        notification_id = session.scalar(select(NotificationModel.notification_id).where(
            NotificationModel.recipient_user_id == workflow.users["recipient"],
        ))
    path = f"notifications/{notification_id}/read"
    assert workflow.post(path).status_code == 404
    first = workflow.post(path, "recipient")
    assert first.status_code == 200
    assert first.json()["read_at"] is not None
    assert workflow.post(path, "recipient").json() == first.json()


@pytest.mark.parametrize("race", ["create", "review", "cancel_sign"])
def test_concurrent_mutations_serialize_without_partial_effects(workflow, race):
    assignment_id = None if race == "create" else workflow.assign().json()["assignment_id"]
    barrier = Barrier(2)

    def run(index):
        actor = "manager" if race == "create" or (race == "cancel_sign" and index == 0) else "recipient"
        with Session(workflow.runtime_engine) as session:
            repository = DocumentAccessRepositoryPg(session, {"user_id": int(workflow.users[actor])})
            barrier.wait(timeout=10)
            try:
                if race == "create":
                    result = repository.create_assignment(workflow.documents["owned"], workflow.users["recipient"])
                elif race == "review":
                    result = repository.update_assignment_status(assignment_id, "ACCEPTED" if index == 0 else "REJECTED", reason="Review")
                elif index == 0:
                    result = repository.cancel_assignment(assignment_id)
                else:
                    result = repository.update_assignment_status(assignment_id, "SIGNED", signature_value="Synthetic")
                return result.assignment_id
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, index) for index in range(2)]
        results = [future.result(timeout=20) for future in futures]
    if race == "create":
        assert results[0] == results[1]
        assert counts(workflow) == (1, 1, 1, 1)
    elif race == "review":
        assert results.count("conflict") == 1
        assert counts(workflow) == (1, 2, 2, 2)
        with Session(workflow.engine) as session:
            status = session.get(DocumentAssignmentModel, assignment_id).status
            assert set(session.scalars(select(DocumentAssignmentEventModel.action).where(
                DocumentAssignmentEventModel.assignment_id == assignment_id,
            ))) == {"ASSIGNED", status}
            assert set(session.scalars(select(AuditLogModel.action).where(
                AuditLogModel.resource_id == assignment_id,
            ))) == {"DOCUMENT_ASSIGNED", f"DOCUMENT_ASSIGNMENT_{status}"}
    else:
        with Session(workflow.engine) as session:
            assert session.get(DocumentAssignmentModel, assignment_id).status == "CANCELLED"
        expected = 2 if "conflict" in results else 3
        assert counts(workflow) == (1, expected, expected, expected)
