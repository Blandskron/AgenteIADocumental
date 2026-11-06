import json
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.infrastructure.database.models import TransferEventModel
from app.infrastructure.database.repositories.transfer_repository_pg import TransferRepositoryPg
from app.main import app


OPERATIONS = [
    ("GET", "/transfers", None),
    ("POST", "/transfers", {"filename": "synthetic.txt", "direction": "UPLOAD"}),
    ("PATCH", "/transfers/synthetic", {"progress": 10}),
    ("DELETE", "/transfers/history", None),
]


def authorization(key, **claims):
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access", **claims}, key, algorithm="RS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("method,path,payload", OPERATIONS)
@pytest.mark.parametrize("claims", [
    {"user_id": None}, {"user_id": True}, {"user_id": False}, {"user_id": 0}, {"user_id": -1},
    {"user_id": "42"}, {"user_id": 42.0}, {"user_id": []}, {"user_id": {}},
    {"exp": None}, {"exp": "4102444800"}, {"exp": 4102444800.5}, {"exp": []}, {"exp": {}},
    {"exp": True}, {"exp": 1}, {"exp": float("inf")},
    {"token_type": "refresh"}, {"token_type": None},
])
def test_invalid_claims_never_reach_repository(configured_client, signing_key, monkeypatch, claims, method, path, payload):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid identity reached the repository")
    monkeypatch.setattr(TransferRepositoryPg, "__init__", forbidden)
    client, _ = configured_client
    response = client.request(method, f"/api/v1{path}", json=payload, headers=authorization(signing_key, **claims))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("missing", ["user_id", "exp"])
def test_required_claims_cannot_use_fallback(configured_client, signing_key, missing):
    claims = {"user_id": 42, "exp": 4102444800, "token_type": "access", "sub": "42", "username": "42"}
    del claims[missing]
    headers = {"Authorization": "Bearer " + jwt.encode(claims, signing_key, algorithm="RS256")}
    client, _ = configured_client
    for method, path, payload in OPERATIONS:
        assert client.request(method, f"/api/v1{path}", json=payload, headers=headers).status_code == 401


@pytest.mark.parametrize("algorithm", ["HS256", "none", "foreign_rsa"])
def test_wrong_algorithm_or_signature_is_rejected(configured_client, signing_key, algorithm):
    claims = {"user_id": 42, "exp": 4102444800, "token_type": "access"}
    key = "synthetic-only-hmac-key-long-enough-for-test" if algorithm == "HS256" else ""
    actual = algorithm
    if algorithm == "foreign_rsa":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        actual = "RS256"
    token = jwt.encode(claims, key, algorithm=actual)
    client, _ = configured_client
    for method, path, payload in OPERATIONS:
        assert client.request(method, f"/api/v1{path}", json=payload,
                              headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("missing", [False, True])
def test_unavailable_public_key_returns_401(configured_client, signing_key, missing):
    client, settings = configured_client
    path = Path(settings.auth_jwt_public_key_path)
    if missing:
        path.unlink()
    else:
        path.write_text("Synthetic malformed public key", encoding="utf-8")
    response = client.get("/api/v1/transfers", headers=authorization(signing_key))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.fixture
def records(configured_client, engine):
    client, _ = configured_client
    tenant, foreign = uuid4().hex, uuid4().hex
    kinds = ("owned", "legacy_owner", "owner_conflict", "empty_owner", "tenant_conflict", "legacy_tenant",
             "group", "foreign_group", "global_group", "legacy_group", "assigned", "managed", "cancelled", "expired", "private")
    documents = {kind: uuid4().hex for kind in kinds}
    events = {kind: uuid4().hex for kind in ("mine", "foreign", "unknown", "legacy", "padded")}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic Transfer')"), [{"id": tenant}, {"id": foreign}])
                for kind, identifier in documents.items():
                    metadata = {
                        "owned": {"owner_user_id": "43"}, "legacy_owner": {"owner_user_id": 42},
                        "owner_conflict": {"owner_user_id": "42"}, "empty_owner": {"owner_user_id": "42"},
                        "tenant_conflict": {"tenant_id": tenant}, "legacy_tenant": {"tenant_id": tenant},
                        "group": {"owner_groups": ["readers"]}, "foreign_group": {"owner_groups": ["readers"]},
                        "global_group": {"owner_groups": ["readers"]},
                        "legacy_group": {"owner_groups": ["readers"], "tenant_id": tenant},
                    }.get(kind, {})
                    session.execute(text("""
                        INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, metadata)
                        VALUES (:id, :tenant, :owner, 'synthetic.txt', 'synthetic.txt', 'text/plain', CAST(:metadata AS jsonb))
                    """), {"id": identifier, "tenant": foreign if kind in ("tenant_conflict", "foreign_group") else (
                        None if kind in ("legacy_tenant", "global_group", "legacy_group") else tenant),
                        "owner": "42" if kind == "owned" else None if kind == "legacy_owner" else "" if kind == "empty_owner" else "43",
                        "metadata": json.dumps(metadata)})
                session.execute(text("""
                    INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id, status)
                    VALUES (:id, :tenant, :recipient, :sender, :status)
                """), [{"id": documents[kind], "tenant": tenant, "recipient": recipient, "sender": sender, "status": status}
                       for kind, recipient, sender, status in (
                           ("assigned", "42", "43", "PENDING"), ("managed", "43", "42", "VIEWED"),
                           ("cancelled", "42", "43", "CANCELLED"), ("expired", "43", "42", "EXPIRED"))])
                session.execute(text("""
                    INSERT INTO transfer_events (transfer_id, owner_user_id, filename, direction, status, progress)
                    VALUES (:id, :owner, 'synthetic.txt', 'UPLOAD', 'COMPLETED', 100)
                """), [{"id": events[kind], "owner": owner} for kind, owner in (
                    ("mine", "42"), ("foreign", "43"), ("unknown", "unknown"), ("legacy", "synthetic-username"), ("padded", "042"))])
                session.commit()
                app.dependency_overrides[get_session] = lambda: session
                yield client, session, documents, events, tenant, foreign
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=ANY(:ids)"), {"ids": list(documents.values())}) == 0
        assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE transfer_id=ANY(:ids)"), {"ids": list(events.values())}) == 0


BASE = {"owned", "legacy_owner", "assigned", "managed"}
ALL = BASE | {"owner_conflict", "empty_owner", "tenant_conflict", "legacy_tenant", "group", "foreign_group",
              "global_group", "legacy_group", "cancelled", "expired", "private"}


@pytest.mark.parametrize("actor,expected", [
    ("reader", BASE), ("group_without_membership", BASE | {"global_group"}),
    ("group_member", BASE | {"group", "global_group", "legacy_group"}),
    ("tenant_admin", ALL - {"tenant_conflict", "foreign_group", "global_group"}),
    ("foreign_admin", BASE | {"tenant_conflict", "foreign_group"}), ("superadmin", ALL),
])
@pytest.mark.parametrize("operation", ["create", "patch"])
def test_reference_policy_matches_library(records, signing_key, actor, expected, operation):
    client, session, documents, events, tenant, foreign = records
    claims = {
        "group_without_membership": {"groups": ["readers"]},
        "group_member": {"groups": ["readers"], "tenant_memberships": [{"tenant_id": tenant, "role": "USER"}]},
        "tenant_admin": {"tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}]},
        "foreign_admin": {"tenant_memberships": [{"tenant_id": foreign, "role": "TENANT_ADMIN"}]},
        "superadmin": {"is_superadmin": True},
    }.get(actor, {})
    headers = authorization(signing_key, **claims)
    for kind, identifier in {**documents, "missing": uuid4().hex}.items():
        if operation == "create":
            response = client.post("/api/v1/transfers", headers=headers,
                                   json={"filename": "synthetic.txt", "direction": "DOWNLOAD", "document_id": identifier})
        else:
            response = client.patch(f"/api/v1/transfers/{events['mine']}", headers=headers, json={"document_id": identifier})
        assert response.status_code == (200 if kind in expected else 404), (actor, kind, response.text)
        if kind in expected:
            assert response.json()["document_id"] == identifier
        else:
            assert response.json() == {"detail": "Document not found."}
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id=ANY(:ids)"), {"ids": list(documents.values())}) == len(documents)


@pytest.mark.parametrize("admin", [False, True])
def test_history_stays_private_and_legacy_owners_are_untouched(records, signing_key, admin):
    client, session, documents, events, _, _ = records
    headers = authorization(signing_key, sub="43", username="unknown", is_superadmin=admin)
    response = client.get("/api/v1/transfers", headers=headers)
    assert {row["transfer_id"] for row in response.json()["items"]} == {events["mine"]}
    for identifier in (events["foreign"], events["unknown"], events["legacy"], events["padded"], uuid4().hex):
        response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"document_id": documents["owned"]})
        assert response.status_code == 404 and response.json() == {"detail": "Transfer not found."}
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 1}
    remaining = dict(session.execute(text("SELECT transfer_id, owner_user_id FROM transfer_events WHERE transfer_id=ANY(:ids)"),
                                    {"ids": list(events.values())}).all())
    assert remaining == {events[kind]: owner for kind, owner in (
        ("foreign", "43"), ("unknown", "unknown"), ("legacy", "synthetic-username"), ("padded", "042"))}
    created = client.post("/api/v1/transfers", headers=headers, json={
        "filename": "synthetic.txt", "direction": "UPLOAD", "owner_user_id": "43"})
    assert created.status_code == 422


@pytest.mark.parametrize("kind", ["assigned", "managed"])
@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED"])
def test_revocation_rejects_new_references_but_preserves_personal_journal(records, signing_key, kind, status):
    client, session, documents, events, _, _ = records
    headers = authorization(signing_key)
    identifier = documents[kind]
    payload = {"filename": "synthetic.txt", "direction": "DOWNLOAD", "document_id": identifier}
    created = client.post("/api/v1/transfers", headers=headers, json=payload)
    assert created.status_code == 200
    event = created.json()["transfer_id"]
    session.execute(text("UPDATE document_assignments SET status=:status WHERE document_id=:id"), {"status": status, "id": identifier})
    session.commit()
    assert client.post("/api/v1/transfers", headers=headers, json=payload).status_code == 404
    assert client.patch(f"/api/v1/transfers/{events['mine']}", headers=headers, json={"document_id": identifier}).status_code == 404
    # Updating an owned journal without a new reference grants no document access.
    assert client.patch(f"/api/v1/transfers/{event}", headers=headers, json={"progress": 50}).status_code == 200
    rows = client.get("/api/v1/transfers", headers=headers).json()["items"]
    assert next(row for row in rows if row["transfer_id"] == event)["document_id"] == identifier


def test_document_delete_preserves_event_and_clear_preserves_document(records, signing_key):
    client, session, documents, _, _, _ = records
    headers = authorization(signing_key)
    created = client.post("/api/v1/transfers", headers=headers, json={
        "filename": "synthetic.txt", "direction": "UPLOAD", "document_id": documents["owned"]})
    event = created.json()["transfer_id"]
    session.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": documents["owned"]})
    session.commit()
    session.expire_all()
    rows = client.get("/api/v1/transfers", headers=headers).json()["items"]
    assert next(row for row in rows if row["transfer_id"] == event)["document_id"] is None
    assert client.delete("/api/v1/transfers/history", headers=headers).status_code == 200
    assert session.scalar(select(TransferEventModel.transfer_id).where(TransferEventModel.transfer_id == event)) == event
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": documents["private"]}) == 1


def test_owner_audit_is_aggregate_and_nonmutating(engine):
    script = Path("/transfer-db/audit_owners.sql").read_text(encoding="utf-8")
    query = script.split("BEGIN READ ONLY;", 1)[1].split("COMMIT;", 1)[0]
    # Execute exactly the audit SELECT against a temporary projection, without shared data.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE TEMP TABLE transfer_events (owner_user_id text)"))
            owners = ["42", "42", "unknown", "042", "0", "-1", "True", "synthetic-username", ""]
            connection.execute(text("INSERT INTO pg_temp.transfer_events VALUES (:owner)"), [{"owner": owner} for owner in owners])
            counts = dict(connection.execute(text(query.replace("public.transfer_events", "pg_temp.transfer_events"))).all())
            assert counts == {"canonical_numeric_unverified": 2, "unresolved_unknown": 1,
                              "noncanonical_numeric": 2, "noncanonical_other": 4}
            assert connection.scalars(text("SELECT owner_user_id FROM pg_temp.transfer_events")).all() == owners
        finally:
            transaction.rollback()
