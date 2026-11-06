import json
from os import environ
from secrets import token_bytes
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.interfaces.api.v1.dependencies import get_library_use_case
from app.main import app


def authorization(key, **claims):
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access", **claims}, key, algorithm="RS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def records(configured_client, monkeypatch):
    client, _ = configured_client
    engine = create_engine(environ["LIBRARY_TEST_DATABASE_URL"])
    tenant, foreign_tenant = uuid4().hex, uuid4().hex
    kinds = (
        "owned", "legacy_owner", "owner_conflict", "empty_owner", "tenant_conflict", "legacy_tenant",
        "group", "foreign_group", "global_group", "legacy_group", "assigned", "managed", "cancelled", "expired",
        "private", "nonprocessed",
    )
    documents = {kind: uuid4().hex for kind in kinds}
    folders = {kind: uuid4().hex for kind in ("mine", "empty", "child", "foreign", "foreign_child")}
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic LIB003')"), [
                        {"id": tenant}, {"id": foreign_tenant},
                    ])
                    for kind, document_id in documents.items():
                        metadata = {
                            "owned": {"owner_user_id": "43"}, "legacy_owner": {"owner_user_id": 42},
                            "owner_conflict": {"owner_user_id": "42"}, "empty_owner": {"owner_user_id": "42"},
                            "tenant_conflict": {"tenant_id": tenant}, "legacy_tenant": {"tenant_id": tenant},
                            "group": {"owner_groups": ["readers"]}, "foreign_group": {"owner_groups": ["readers"]},
                            "global_group": {"owner_groups": ["readers"]},
                            "legacy_group": {"tenant_id": tenant, "owner_groups": ["readers"]},
                        }.get(kind, {})
                        session.execute(text("""
                            INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, status, metadata)
                            VALUES (:id, :tenant, :owner, :filename, 'synthetic-lib003.txt', 'text/plain', :status, CAST(:metadata AS jsonb))
                        """), {
                            "id": document_id,
                            "tenant": foreign_tenant if kind in ("tenant_conflict", "foreign_group") else (
                                None if kind in ("legacy_tenant", "global_group", "legacy_group") else tenant),
                            "owner": "42" if kind in ("owned", "nonprocessed") else (
                                None if kind == "legacy_owner" else "" if kind == "empty_owner" else "43"),
                            "filename": f"{kind}.txt", "status": "PENDING" if kind == "nonprocessed" else "PROCESSED",
                            "metadata": json.dumps(metadata),
                        })
                    session.execute(text("""
                        INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
                        VALUES (:id, 0, 'Synthetic fragment', array_fill(1.0::real, ARRAY[384])::vector)
                    """), [{"id": identifier} for identifier in documents.values()])
                    session.execute(text("INSERT INTO document_folders (folder_id, name, parent_folder_id, owner_user_id) VALUES (:id, :name, :parent, :owner)"), [
                        {"id": identifier, "name": f"Synthetic {kind}",
                         "parent": folders["mine"] if kind == "child" else folders["foreign"] if kind == "foreign_child" else None,
                         "owner": "43" if kind in ("foreign", "foreign_child") else "42"}
                        for kind, identifier in folders.items()
                    ])
                    session.execute(text("INSERT INTO document_folder_items (folder_id, document_id, owner_user_id) VALUES (:folder, :document, :owner)"), [
                        *[{"folder": folders["mine"], "document": identifier, "owner": "42"} for identifier in documents.values()],
                        {"folder": folders["foreign"], "document": documents["owned"], "owner": "43"},
                    ])
                    session.execute(text("INSERT INTO document_favorites (document_id, owner_user_id) VALUES (:id, '42')"), [
                        {"id": identifier} for identifier in documents.values()
                    ])
                    session.execute(text("""
                        INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id, status)
                        VALUES (:id, :tenant, :recipient, :sender, :status)
                    """), [
                        {"id": documents[kind], "tenant": tenant, "recipient": recipient, "sender": sender, "status": status}
                        for kind, recipient, sender, status in (
                            ("assigned", "42", "43", "PENDING"), ("managed", "43", "42", "VIEWED"),
                            ("managed", "44", "42", "ACCEPTED"), ("cancelled", "42", "43", "CANCELLED"),
                            ("expired", "43", "42", "EXPIRED"),
                        )
                    ])
                    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
                    yield client, session, documents, folders, tenant, foreign_tenant
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


BASE = {"owned", "legacy_owner", "assigned", "managed", "nonprocessed"}
ALL = BASE | {"owner_conflict", "empty_owner", "tenant_conflict", "legacy_tenant", "group", "foreign_group",
              "global_group", "legacy_group", "cancelled", "expired", "private"}


@pytest.mark.parametrize("actor,expected", [
    ("reader", BASE), ("group_without_membership", BASE | {"global_group"}),
    ("group_member", BASE | {"group", "global_group", "legacy_group"}),
    ("tenant_admin", ALL - {"tenant_conflict", "foreign_group", "global_group"}),
    ("foreign_admin", BASE | {"tenant_conflict", "foreign_group"}), ("superadmin", ALL),
])
def test_all_lists_and_counts_use_one_document_policy(records, signing_key, actor, expected):
    client, _, documents, folders, tenant, foreign = records
    claims = {
        "group_without_membership": {"groups": ["readers"]},
        "group_member": {"groups": ["readers"], "tenant_memberships": [{"tenant_id": tenant, "role": "USER"}]},
        "tenant_admin": {"tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}]},
        "foreign_admin": {"tenant_memberships": [{"tenant_id": foreign, "role": "TENANT_ADMIN"}]},
        "superadmin": {"is_superadmin": True},
    }.get(actor, {})
    headers = authorization(signing_key, **claims)
    expected_ids = {documents[kind] for kind in expected}
    for path in ("/library/recent?limit=100", "/library/favorites", f"/folders/{folders['mine']}/documents"):
        response = client.get(f"/api/v1{path}", headers=headers)
        assert response.status_code == 200
        rows = response.json()["items"]
        assert {row["document_id"] for row in rows} == expected_ids - (
            {documents["nonprocessed"]} if path.startswith("/library/recent") else set())
        assert all(row["chunk_count"] == 1 for row in rows)
        assert all(set(row) == {"document_id", "filename", "mime_type", "status", "chunk_count", "updated_at", "is_favorite"} for row in rows)
    rows = client.get("/api/v1/folders", headers=headers).json()["items"]
    assert {row["folder_id"] for row in rows} == {folders["mine"], folders["empty"]}
    assert next(row["document_count"] for row in rows if row["folder_id"] == folders["mine"]) == len(expected_ids)
    assert next(row["document_count"] for row in rows if row["folder_id"] == folders["empty"]) == 0


@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED"])
@pytest.mark.parametrize("kind", ["assigned", "managed"])
def test_revocation_is_visible_in_each_subsequent_request(records, signing_key, kind, status):
    client, session, documents, folders, _, _ = records
    headers = authorization(signing_key)
    identifier = documents[kind]
    path = f"/api/v1/folders/{folders['mine']}/documents"
    assert identifier in {row["document_id"] for row in client.get(path, headers=headers).json()["items"]}
    session.execute(text("UPDATE document_assignments SET status = :status WHERE document_id = :id"), {"status": status, "id": identifier})
    for path in (path, "/api/v1/library/favorites", "/api/v1/library/recent?limit=100"):
        assert identifier not in {row["document_id"] for row in client.get(path, headers=headers).json()["items"]}
    rows = client.get("/api/v1/folders", headers=headers).json()["items"]
    assert next(row["document_count"] for row in rows if row["folder_id"] == folders["mine"]) == len(BASE) - 1


@pytest.mark.parametrize("superadmin", [False, True])
def test_folders_remain_private(records, signing_key, superadmin):
    client, session, documents, folders, _, _ = records
    headers = authorization(signing_key, is_superadmin=superadmin)
    for identifier in (folders["foreign"], uuid4().hex):
        response = client.get(f"/api/v1/folders/{identifier}/documents", headers=headers)
        assert response.status_code == 404 and response.json() == {"detail": "Folder not found."}
        response = client.get(f"/api/v1/folders?parent_folder_id={identifier}", headers=headers)
        assert response.status_code == 404 and response.json() == {"detail": "Folder not found."}
    response = client.delete(f"/api/v1/folders/{folders['foreign']}/documents/{documents['private']}", headers=headers)
    assert response.json() == {"deleted": False}
    assert session.scalar(text("SELECT count(*) FROM document_folder_items WHERE folder_id=:id AND owner_user_id='42'"), {"id": folders["foreign"]}) == 0
    assert client.patch(f"/api/v1/folders/{folders['foreign']}", json={"name": "Forbidden"}, headers=headers).status_code == 404
    assert client.delete(f"/api/v1/folders/{folders['foreign']}", headers=headers).json() == {"deleted": False}


def test_valid_identity_has_precedence_over_sub_and_username(records, signing_key):
    client, _, _, folders, _, _ = records
    rows = client.get("/api/v1/folders", headers=authorization(signing_key, sub="43", username="43")).json()["items"]
    assert {row["folder_id"] for row in rows} == {folders["mine"], folders["empty"]}


def test_owner_parent_and_superadmin_item_owner_are_checked(records, signing_key):
    client, _, documents, folders, _, _ = records
    response = client.get(f"/api/v1/folders?parent_folder_id={folders['mine']}", headers=authorization(signing_key))
    assert {row["folder_id"] for row in response.json()["items"]} == {folders["child"]}
    headers = authorization(signing_key, user_id=43, is_superadmin=True)
    response = client.get(f"/api/v1/folders/{folders['foreign']}/documents", headers=headers)
    assert {row["document_id"] for row in response.json()["items"]} == {documents["owned"]}
    rows = client.get("/api/v1/folders", headers=headers).json()["items"]
    assert {row["folder_id"] for row in rows} == {folders["foreign"]}
    assert rows[0]["document_count"] == 1
    headers = authorization(signing_key, user_id=43)
    assert client.get(f"/api/v1/folders/{folders['foreign']}/documents", headers=headers).json()["items"] == []
    assert client.get("/api/v1/folders", headers=headers).json()["items"][0]["document_count"] == 0


@pytest.mark.parametrize("kind", ["private", "cancelled", "expired", "owner_conflict", "foreign_group"])
def test_inaccessible_document_cannot_be_added_or_moved(records, signing_key, kind):
    client, session, documents, folders, _, _ = records
    headers = authorization(signing_key)
    identifier = documents[kind]
    response = client.post(f"/api/v1/folders/{folders['empty']}/documents/{identifier}", headers=headers)
    assert response.json() == {"deleted": False}
    assert client.patch(f"/api/v1/library/documents/{identifier}/folder", json={"folder_id": folders["empty"]}, headers=headers).status_code == 404
    assert client.post(f"/api/v1/library/favorites/{identifier}", headers=headers).json() == {"count": 0}
    assert session.scalar(text("SELECT count(*) FROM document_folder_items WHERE folder_id=:id"), {"id": folders["empty"]}) == 0
    assert session.scalar(text("SELECT count(*) FROM document_folder_items WHERE folder_id=:folder AND document_id=:doc"), {
        "folder": folders["mine"], "doc": identifier,
    }) == 1


def test_revoked_markers_can_be_removed_without_read_access(records, signing_key):
    client, session, documents, folders, _, _ = records
    headers = authorization(signing_key)
    identifier = documents["cancelled"]
    assert client.delete(f"/api/v1/library/favorites/{identifier}", headers=headers).json() == {"count": 1}
    assert client.delete(f"/api/v1/folders/{folders['mine']}/documents/{identifier}", headers=headers).json() == {"deleted": True}
    assert session.scalar(text("SELECT count(*) FROM document_favorites WHERE document_id=:id AND owner_user_id='42'"), {"id": identifier}) == 0
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == 1


def test_private_folder_creation_and_association_positive_paths(records, signing_key):
    client, session, documents, folders, _, _ = records
    headers = authorization(signing_key)
    created = client.post("/api/v1/folders", json={"name": "Synthetic created", "parent_folder_id": folders["mine"]}, headers=headers)
    assert created.status_code == 201 and created.json()["owner_user_id"] == "42"
    assert client.patch(f"/api/v1/folders/{created.json()['folder_id']}", json={"name": "Synthetic renamed"}, headers=headers).status_code == 200
    assert client.post("/api/v1/folders", json={"name": "Forbidden", "parent_folder_id": folders["foreign"]}, headers=headers).status_code == 404
    identifier, destination = documents["owned"], created.json()["folder_id"]
    assert client.post(f"/api/v1/folders/{destination}/documents/{identifier}", headers=headers).json() == {"deleted": True}
    assert client.patch(f"/api/v1/library/documents/{identifier}/folder", json={"folder_id": folders["empty"]}, headers=headers).json() == {"success": True}
    assert session.scalars(text("SELECT folder_id FROM document_folder_items WHERE document_id=:id AND owner_user_id='42'"), {"id": identifier}).all() == [folders["empty"]]
    assert client.delete(f"/api/v1/folders/{folders['empty']}", headers=headers).json() == {"deleted": True}
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == 1


@pytest.mark.parametrize("payload", [
    {"exp": 4102444800}, {"user_id": 42}, {"user_id": None}, {"user_id": True}, {"user_id": False},
    {"user_id": 0}, {"user_id": -1}, {"user_id": "42"}, {"user_id": 1.5}, {"user_id": []}, {"user_id": {}},
    {"user_id": 42, "exp": "4102444800"}, {"user_id": 42, "exp": 4102444800.0},
    {"user_id": 42, "exp": None}, {"user_id": 42, "exp": []}, {"user_id": 42, "exp": float("inf")},
    {"user_id": 42, "exp": 1}, {"user_id": 42, "token_type": "refresh"}, {"sub": "42", "username": "42"},
])
def test_invalid_identity_or_expiration_never_reaches_library(configured_client, signing_key, monkeypatch, payload):
    client, _ = configured_client
    claims = {"token_type": "access", **payload}
    # Missing required claims stay missing in the two explicit absence cases.
    if payload not in ({"exp": 4102444800}, {"user_id": 42}):
        claims.setdefault("exp", 4102444800)

    def forbidden_use_case():
        pytest.fail("Invalid claims reached the library")

    monkeypatch.setitem(app.dependency_overrides, get_library_use_case, forbidden_use_case)
    token = jwt.encode(claims, signing_key, algorithm="RS256")
    response = client.post("/api/v1/folders", json={"name": "Must not be written"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("algorithm", ["wrong_rsa_key", "HS256", "none"])
def test_other_keys_or_algorithms_are_rejected(configured_client, algorithm):
    client, _ = configured_client
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if algorithm == "wrong_rsa_key" else (
        None if algorithm == "none" else token_bytes(32))
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, key,
                       algorithm="RS256" if algorithm == "wrong_rsa_key" else algorithm)
    response = client.get("/api/v1/folders", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
