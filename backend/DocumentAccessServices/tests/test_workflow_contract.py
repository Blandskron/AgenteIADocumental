from uuid import uuid4

import pytest

from app.interfaces.api.v1.schemas.document_access_schema import DocumentAssignmentCreateRequest
from test_assignments import change, counts


@pytest.mark.parametrize("fields", [
    {"assigned_to_user_id": "0"}, {"assigned_to_user_id": "x"}, {"assigned_to_user_id": "1" * 20},
    {"assigned_to_user_id": "1\x00"}, {"metadata": {"key": "é" * 8192}},
    {"metadata": {"key": "\x00"}}, {"metadata": {"\x00": "value"}},
    {"metadata": {"nested": ["\x00"]}}, {"unexpected": True},
])
def test_invalid_assignment_input_is_rejected_without_effects(workflow, fields):
    response = workflow.post(f"{workflow.documents['owned']}/assignments", payload={
        "assigned_to_user_id": workflow.users["recipient"], **fields,
    })
    assert response.status_code == 422
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
    assert counts(workflow) == (0, 0, 0, 0)


def test_metadata_json_limits():
    from pydantic import ValidationError

    for invalid in ({"number": float("nan")}, {"number": float("inf")}):
        with pytest.raises(ValidationError):
            DocumentAssignmentCreateRequest(assigned_to_user_id="1", metadata=invalid)
    nested = {}
    for _ in range(18):
        nested = {"nested": nested}
    with pytest.raises(ValidationError):
        DocumentAssignmentCreateRequest(assigned_to_user_id="1", metadata=nested)
    assert DocumentAssignmentCreateRequest(assigned_to_user_id="1", metadata={"key": "x" * 16374}).metadata


def test_oversized_http_body_is_rejected_before_writes(workflow):
    response = workflow.assign(metadata={"large": "x" * 65_536})
    assert response.status_code == 413
    assert counts(workflow) == (0, 0, 0, 0)


@pytest.mark.parametrize("action,payload", [("reject", {"reason": "x" * 2000}), ("sign", {"signature_value": "x" * 4096})])
def test_action_size_boundaries_remain_usable(workflow, action, payload):
    assignment_id = workflow.assign().json()["assignment_id"]
    assert workflow.post(f"assignments/{assignment_id}/{action}", "recipient", payload).status_code == 200


@pytest.mark.parametrize("action,field,value", [
    ("reject", "reason", "x" * 2001), ("sign", "signature_value", "x" * 4097),
    ("reject", "reason", "\x00"), ("sign", "signature_value", "\x00"),
])
def test_action_input_limits_prevent_writes_and_value_reflection(workflow, action, field, value):
    assignment_id = workflow.assign().json()["assignment_id"]
    response = workflow.post(f"assignments/{assignment_id}/{action}", "recipient", {field: value})
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])
    assert counts(workflow) == (1, 1, 1, 1)


@pytest.mark.parametrize("path", ["assigned-to-me", "managed-by-me", "notifications", "assignments/missing/events"])
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "offset=100001", "limit=abc"])
def test_pagination_parameters_are_bounded(workflow, path, query):
    assert workflow.get(f"{path}?{query}").status_code == 422


@pytest.mark.parametrize("path", ["{id}/content", "assignments/{id}/events"])
def test_path_identifier_limits(workflow, path):
    for invalid in ("x" * 129, "%00"):
        assert workflow.get(path.format(id=invalid)).status_code == 422


def test_invalid_notification_filter_and_hidden_events(workflow):
    assert workflow.get("notifications?status=unknown").status_code == 422
    assert workflow.get("notifications?status=ARCHIVED").json()["items"] == []
    assignment_id = workflow.assign().json()["assignment_id"]
    assert workflow.get(f"assignments/{assignment_id}/events", "outsider").status_code == 404
    assert workflow.get("assignments/missing/events", "outsider").status_code == 404


def seed_pages(workflow):
    ids = []
    for index in range(3):
        name, document_id = f"page{index}", uuid4().hex
        workflow.documents[name] = document_id
        change(workflow, """
            INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type)
            VALUES (:id, :tenant, :owner, 'synthetic.txt', 'synthetic.txt', 'text/plain')
        """, id=document_id, tenant=workflow.tenant, owner=workflow.users["manager"])
        response = workflow.assign(document=name)
        assert response.status_code == 200
        ids.append(response.json()["assignment_id"])
    assert workflow.assign(actor="outsider", recipient="outsider", document="foreign").status_code == 200
    # Equal timestamps exercise the identifier tie-breaker rather than insertion order.
    change(workflow, "UPDATE document_assignments SET created_at = '2020-01-01' WHERE tenant_id = :tenant", tenant=workflow.tenant)
    change(workflow, "UPDATE notifications SET created_at = '2020-01-01' WHERE tenant_id = :tenant", tenant=workflow.tenant)
    return ids


@pytest.mark.parametrize("path,actor,key", [
    ("assigned-to-me", "recipient", "assignment_id"), ("managed-by-me", "manager", "assignment_id"),
    ("notifications", "recipient", "notification_id"),
])
def test_scoped_pages_have_stable_order_and_no_missing_rows(workflow, path, actor, key):
    ids = seed_pages(workflow)
    first = workflow.get(f"{path}?limit=2", actor).json()
    second = workflow.get(f"{path}?limit=2&offset=2", actor).json()
    assert (first["limit"], first["offset"], first["has_more"]) == (2, 0, True)
    assert (second["offset"], second["has_more"]) == (2, False)
    rows = first["items"] + second["items"]
    assert len(rows) == 3
    assert [row[key] for row in rows] == sorted((row[key] for row in rows), reverse=True)
    assert all(row["tenant_id"] == workflow.tenant for row in rows)
    if key == "assignment_id":
        assert set(row[key] for row in rows) == set(ids)
    assert workflow.get(f"{path}?offset=100", actor).json()["items"] == []


def test_event_pages_and_notification_filter(workflow):
    assignment_id = workflow.assign().json()["assignment_id"]
    assert workflow.post(f"assignments/{assignment_id}/accept", "recipient").status_code == 200
    assert workflow.post(f"assignments/{assignment_id}/sign", "recipient", {"signature_value": "Synthetic"}).status_code == 200
    change(workflow, "UPDATE document_assignment_events SET created_at = '2020-01-01' WHERE assignment_id = :id", id=assignment_id)
    first = workflow.get(f"assignments/{assignment_id}/events?limit=2").json()
    second = workflow.get(f"assignments/{assignment_id}/events?limit=2&offset=2").json()
    rows = first["items"] + second["items"]
    assert first["has_more"] and not second["has_more"]
    assert len(rows) == 3
    assert [row["event_id"] for row in rows] == sorted(row["event_id"] for row in rows)
    assert {row["action"] for row in rows} == {"ASSIGNED", "ACCEPTED", "SIGNED"}
    notification = workflow.get("notifications?status=UNREAD", "recipient").json()["items"][0]
    workflow.post(f"notifications/{notification['notification_id']}/read", "recipient")
    assert workflow.get("notifications?status=UNREAD", "recipient").json()["items"] == []
    assert len(workflow.get("notifications?status=READ", "recipient").json()["items"]) == 1
