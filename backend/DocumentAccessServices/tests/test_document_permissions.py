import json
from os import environ
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import get_settings
from app.interfaces.api.v1.dependencies import get_path_resolver
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.main import app
from app.shared.constants import MAX_CONTENT_CHARACTERS


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def authorization(signing_key, **claims):
    token = jwt.encode({
        "user_id": 42, "exp": 4102444800, "token_type": "access", **claims,
    }, signing_key, algorithm="RS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def records(tmp_path):
    engine = create_engine(environ["ACCESS_TEST_DATABASE_URL"])
    tenant, foreign_tenant = uuid4().hex, uuid4().hex
    kinds = ("owned", "legacy", "group", "global_group", "foreign", "assigned", "managed", "no_download", "legacy_tenant")
    ids = {kind: uuid4().hex for kind in kinds}
    document_tenants = dict.fromkeys(kinds, tenant)
    document_tenants.update(global_group=None, legacy_tenant=None, foreign=foreign_tenant)
    document_owners = dict.fromkeys(kinds, "43")
    document_owners.update(owned="42", no_download="42", legacy=None)
    (tmp_path / "synthetic.txt").write_text("Synthetic document", encoding="utf-8")
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic')"), [
                        {"id": tenant}, {"id": foreign_tenant},
                    ])
                    session.execute(text("""
                        INSERT INTO documents
                            (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, status, metadata, allow_download)
                        VALUES (:id, :tenant, :owner, :filename, 'synthetic.txt', 'text/plain', 'PROCESSED',
                                CAST(:metadata AS jsonb), :download)
                    """), [
                        {
                            "id": document,
                            "tenant": document_tenants[kind],
                            "owner": document_owners[kind],
                            "filename": f"{kind}.txt",
                            "download": kind != "no_download",
                            "metadata": json.dumps({
                                "owned": {"owner_user_id": "43"},
                                "legacy": {"owner_user_id": 42},
                                "group": {"owner_groups": ["readers"]},
                                "global_group": {"owner_groups": ["readers"]},
                                "foreign": {"owner_user_id": "42", "tenant_id": tenant, "owner_groups": ["readers"]},
                                "legacy_tenant": {"tenant_id": tenant},
                            }.get(kind, {})),
                        }
                        for kind, document in ids.items()
                    ])
                    session.execute(text("""
                        INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
                        VALUES (:id, 0, 'Synthetic content', array_fill(1.0::real, ARRAY[384])::vector)
                    """), [{"id": document} for document in ids.values()])
                    session.execute(text("""
                        INSERT INTO document_assignments
                            (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id, allow_download)
                        VALUES (:id, :tenant, :recipient, :sender, true)
                    """), [
                        {"id": ids["assigned"], "tenant": tenant, "recipient": "42", "sender": "43"},
                        {"id": ids["managed"], "tenant": tenant, "recipient": "43", "sender": "42"},
                    ])
                    yield session, ids, tenant, foreign_tenant
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def client(records, signing_key, tmp_path, monkeypatch):
    session, _, _, _ = records
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    settings = get_settings().model_copy(update={"auth_jwt_public_key_path": str(public_key)})
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)
    def runtime_session():
        session.execute(text("SET LOCAL ROLE document_access_runtime"))
        try:
            yield session
        finally:
            session.execute(text("RESET ROLE"))

    monkeypatch.setitem(app.dependency_overrides, get_session, runtime_session)
    monkeypatch.setitem(app.dependency_overrides, get_path_resolver, lambda: LocalDocumentPathResolver(str(tmp_path)))
    async def paused_cleanup(database, path_resolver, stop):
        await stop.wait()

    monkeypatch.setattr("app.main.deletion_cleanup_loop", paused_cleanup)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("claims", [
    {"exp": 4102444800},
    {"user_id": 42},
    {"user_id": True, "exp": 4102444800},
    {"user_id": "42", "exp": 4102444800},
    {"user_id": 0, "exp": 4102444800},
    {"user_id": -1, "exp": 4102444800},
    {"user_id": 42, "exp": 0},
    {"user_id": 42, "exp": []},
    {"user_id": 42, "exp": True},
    {"user_id": 42, "exp": "4102444800"},
    {"user_id": 42, "exp": 4102444800, "token_type": "refresh"},
])
def test_http_rejects_invalid_identity_and_expiration(client, signing_key, claims):
    token = jwt.encode({
        "token_type": "access", "sub": "42", "username": "42", **claims,
    }, signing_key, algorithm="RS256")
    response = client.get("/api/v1/documents/missing/preview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_http_rejects_missing_or_invalid_signature(client):
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for headers in ({}, authorization(wrong_key), {"Authorization": "Bearer invalid"}):
        response = client.get("/api/v1/documents/missing/preview", headers=headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("actor,allowed", [
    ("owner", {"owned", "legacy", "assigned", "managed", "no_download"}),
    ("group_member", {"owned", "legacy", "assigned", "managed", "no_download", "group", "global_group"}),
    ("group_outsider", {"owned", "legacy", "assigned", "managed", "no_download", "global_group"}),
    ("tenant_admin", {"owned", "legacy", "assigned", "managed", "no_download", "group", "legacy_tenant"}),
    ("foreign_admin", {"foreign"}),
    ("other_owner", {"group", "global_group", "foreign", "assigned", "managed", "legacy_tenant"}),
    ("superadmin", {"owned", "legacy", "assigned", "managed", "no_download", "group", "global_group", "foreign", "legacy_tenant"}),
])
def test_preview_and_content_share_document_permissions(client, records, signing_key, actor, allowed):
    _, ids, tenant, foreign_tenant = records
    claims = {
        "owner": {},
        "group_member": {"groups": ["readers"], "tenant_memberships": [{"tenant_id": tenant}]},
        "group_outsider": {"groups": ["readers"]},
        "tenant_admin": {"user_id": 44, "tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}]},
        "foreign_admin": {"user_id": 44, "tenant_memberships": [{"tenant_id": foreign_tenant, "role": "TENANT_ADMIN"}]},
        "other_owner": {"user_id": 43},
        "superadmin": {"user_id": 45, "is_superadmin": True},
    }[actor]
    headers = authorization(signing_key, **claims)
    for kind, document_id in ids.items():
        preview = client.get(f"/api/v1/documents/{document_id}/preview", headers=headers)
        content = client.get(f"/api/v1/documents/{document_id}/content", headers=headers)
        assert preview.status_code == content.status_code == (200 if kind in allowed else 404), kind
        if kind in allowed:
            assert preview.text == "Synthetic document"
            assert content.json()["content"] == "Synthetic content"


def test_download_requires_its_own_permission(client, records, signing_key):
    session, ids, tenant, _ = records
    headers = authorization(signing_key, groups=["readers"], tenant_memberships=[{"tenant_id": tenant}])
    for kind in ("owned", "legacy", "assigned"):
        response = client.get(f"/api/v1/documents/{ids[kind]}/download", headers=headers)
        assert response.status_code == 200
        assert response.text == "Synthetic document"
    for kind in ("no_download", "group", "global_group", "managed"):
        assert client.get(f"/api/v1/documents/{ids[kind]}/download", headers=headers).status_code == 400
    assert client.get(f"/api/v1/documents/{ids['foreign']}/download", headers=headers).status_code == 404
    session.execute(text("UPDATE document_assignments SET allow_download = false WHERE document_id = :id"), {"id": ids["assigned"]})
    assert client.get(f"/api/v1/documents/{ids['assigned']}/preview", headers=headers).status_code == 200
    assert client.get(f"/api/v1/documents/{ids['assigned']}/download", headers=headers).status_code == 400
    admin = authorization(signing_key, user_id=44, tenant_memberships=[{"tenant_id": tenant, "role": "TENANT_ADMIN"}])
    assert client.get(f"/api/v1/documents/{ids['no_download']}/download", headers=admin).status_code == 200


@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED"])
def test_revocation_removes_recipient_and_sender_access(client, records, signing_key, status):
    session, ids, _, _ = records
    headers = authorization(signing_key)
    for kind in ("assigned", "managed"):
        session.execute(text("UPDATE document_assignments SET status = :status WHERE document_id = :id"), {
            "id": ids[kind], "status": status,
        })
        for suffix in ("preview", "content", "download"):
            response = client.get(f"/api/v1/documents/{ids[kind]}/{suffix}", headers=headers)
            assert response.status_code == 404


@pytest.mark.parametrize("mime_type", ["text/plain", "application/pdf"])
def test_historical_file_uri_headers_and_ranges(client, records, signing_key, tmp_path, mime_type):
    session, ids, _, _ = records
    path = tmp_path / "document ñ.txt"
    path.write_text("Synthetic document", encoding="utf-8")
    session.execute(text("UPDATE documents SET storage_path = :path, mime_type = :mime WHERE document_id = :id"), {
        "id": ids["owned"], "path": path.as_uri(), "mime": mime_type,
    })
    headers = authorization(signing_key)
    base = f"/api/v1/documents/{ids['owned']}"
    preview = client.get(f"{base}/preview", headers=headers)
    download = client.get(f"{base}/download", headers=headers)
    assert preview.status_code == download.status_code == 200
    assert preview.headers["content-disposition"].startswith("inline;")
    assert download.headers["content-disposition"].startswith("attachment;")
    for response in (preview, download):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-type"].split(";")[0] == mime_type
    partial = client.get(f"{base}/preview", headers={**headers, "Range": "bytes=0-8"})
    assert partial.status_code == 206
    assert partial.text == "Synthetic"
    assert partial.headers["content-range"] == "bytes 0-8/18"


@pytest.mark.parametrize("mime_type,expected", [
    ("text/html", "application/octet-stream"),
    ("image/svg+xml", "application/octet-stream"),
    ("text/html\r\nInjected: true", "application/octet-stream"),
    ("text/markdown", "text/markdown"),
])
def test_unsupported_preview_requires_authorized_download(client, records, signing_key, mime_type, expected):
    session, ids, _, _ = records
    session.execute(text("UPDATE documents SET mime_type = :mime WHERE document_id = :id"), {
        "id": ids["owned"], "mime": mime_type,
    })
    base = f"/api/v1/documents/{ids['owned']}"
    headers = authorization(signing_key)
    assert client.get(f"{base}/preview", headers=headers).status_code == 415
    response = client.get(f"{base}/download", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == expected
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "injected" not in response.headers


def test_unicode_filename_is_sanitized_for_delivery(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("UPDATE documents SET filename = :name WHERE document_id = :id"), {
        "id": ids["owned"], "name": "C:\\private\\Contrato ñ\r\n.txt",
    })
    response = client.get(f"/api/v1/documents/{ids['owned']}/download", headers=authorization(signing_key))
    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename*=utf-8''Contrato%20%C3%B1__.txt"


def test_unsupported_preview_preserves_download_denial(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("UPDATE documents SET mime_type = 'text/html' WHERE document_id = :id"), {"id": ids["no_download"]})
    base = f"/api/v1/documents/{ids['no_download']}"
    headers = authorization(signing_key)
    assert client.get(f"{base}/preview", headers=headers).status_code == 415
    assert client.get(f"{base}/download", headers=headers).status_code == 400


def test_missing_file_returns_404_without_recording_download(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("UPDATE documents SET storage_path = 'missing.txt' WHERE document_id = :id"), {"id": ids["owned"]})
    for suffix in ("preview", "download"):
        response = client.get(f"/api/v1/documents/{ids['owned']}/{suffix}", headers=authorization(signing_key))
        assert response.status_code == 404
    assert session.scalar(text("SELECT count(*) FROM audit_logs WHERE resource_id = :id"), {"id": ids["owned"]}) == 0


@pytest.mark.parametrize("first_length,second_length,expected", [
    (MAX_CONTENT_CHARACTERS, None, 200),
    (MAX_CONTENT_CHARACTERS + 1, None, 413),
    (MAX_CONTENT_CHARACTERS // 2, MAX_CONTENT_CHARACTERS // 2 - 2, 200),
    (MAX_CONTENT_CHARACTERS // 2, MAX_CONTENT_CHARACTERS // 2, 413),
])
def test_content_character_budget(client, records, signing_key, first_length, second_length, expected):
    session, ids, _, _ = records
    session.execute(text("UPDATE document_embeddings SET chunk_content = repeat('x', :length) WHERE document_id = :id"), {
        "id": ids["owned"], "length": first_length,
    })
    if second_length is not None:
        session.execute(text("""
            INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
            VALUES (:id, 1, repeat('x', :length), array_fill(1.0::real, ARRAY[384])::vector)
        """), {"id": ids["owned"], "length": second_length})
    response = client.get(f"/api/v1/documents/{ids['owned']}/content", headers=authorization(signing_key))
    assert response.status_code == expected
    if expected == 200:
        assert len(response.json()["content"]) == MAX_CONTENT_CHARACTERS


def test_content_chunk_limit_and_empty_chunks(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("""
        INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
        VALUES (:id, 1, E' \t\n', array_fill(1.0::real, ARRAY[384])::vector)
    """), {"id": ids["owned"]})
    base = f"/api/v1/documents/{ids['owned']}/content"
    headers = authorization(signing_key)
    for limit in (0, 2001):
        assert client.get(base, params={"max_chunks": limit}, headers=headers).status_code == 422
    for limit in (1, 2):
        response = client.get(base, params={"max_chunks": limit}, headers=headers)
        assert response.status_code == 200
        assert response.json()["chunk_count"] == limit
        assert response.json()["content"] == "Synthetic content"


def test_discarded_whitespace_counts_toward_content_budget(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("UPDATE document_embeddings SET chunk_content = repeat(' ', :length) WHERE document_id = :id"), {
        "id": ids["owned"], "length": MAX_CONTENT_CHARACTERS // 2,
    })
    session.execute(text("""
        INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
        VALUES (:id, 1, repeat(' ', :length), array_fill(1.0::real, ARRAY[384])::vector)
    """), {"id": ids["owned"], "length": MAX_CONTENT_CHARACTERS // 2 + 1})
    response = client.get(f"/api/v1/documents/{ids['owned']}/content", headers=authorization(signing_key))
    assert response.status_code == 413


@pytest.fixture
def deletable_file(records, tmp_path):
    session, ids, _, _ = records
    path = tmp_path / "owned-only.txt"
    path.write_text("Synthetic owned file", encoding="utf-8")
    session.execute(text("UPDATE documents SET storage_path = :path WHERE document_id = :id"), {
        "id": ids["owned"], "path": str(path),
    })
    return path


def test_delete_requires_ownership_or_scoped_administration(client, records, signing_key, deletable_file):
    session, ids, tenant, foreign_tenant = records
    for claims in (
        {"user_id": 43},
        {"user_id": 44, "tenant_memberships": [{"tenant_id": foreign_tenant, "role": "TENANT_ADMIN"}]},
    ):
        assert client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key, **claims)).status_code == 404
    reader = authorization(signing_key, groups=["readers"], tenant_memberships=[{"tenant_id": tenant}])
    for kind in ("group", "assigned", "managed"):
        assert client.get(f"/api/v1/documents/{ids[kind]}/preview", headers=reader).status_code == 200
        assert client.delete(f"/api/v1/documents/{ids[kind]}", headers=reader).status_code == 404
    assert deletable_file.exists()
    assert session.scalar(text("SELECT count(*) FROM document_deletions WHERE document_id = :id"), {"id": ids["owned"]}) == 0


@pytest.mark.parametrize("actor", ["owner", "tenant_admin", "superadmin"])
def test_delete_is_idempotent_and_cascades(client, records, signing_key, deletable_file, actor):
    session, ids, tenant, _ = records
    assignment_id = session.scalar(text("""
        INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id)
        VALUES (:id, :tenant, '43', '42') RETURNING assignment_id
    """), {"id": ids["owned"], "tenant": tenant})
    session.execute(text("""
        INSERT INTO document_assignment_events (assignment_id, actor_user_id, action)
        VALUES (:id, '42', 'ASSIGNED')
    """), {"id": assignment_id})
    session.execute(text("""
        INSERT INTO notifications (tenant_id, recipient_user_id, document_id, assignment_id, type, title)
        VALUES (:tenant, '43', :document, :assignment, 'DOCUMENT_ASSIGNMENT', 'Synthetic')
    """), {"tenant": tenant, "document": ids["owned"], "assignment": assignment_id})
    claims = {
        "owner": {},
        "tenant_admin": {"user_id": 44, "tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}]},
        "superadmin": {"user_id": 45, "is_superadmin": True},
    }[actor]
    headers = authorization(signing_key, **claims)
    first = client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers)
    second = client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {
        "document_id": ids["owned"], "filename": "owned.txt", "deleted": True, "file_deleted": True,
    }
    assert not deletable_file.exists()
    for table in ("documents", "document_embeddings", "document_assignments", "notifications"):
        assert session.scalar(text(f"SELECT count(*) FROM {table} WHERE document_id = :id"), {"id": ids["owned"]}) == 0
    assert session.scalar(text("SELECT count(*) FROM document_assignment_events WHERE assignment_id = :id"), {
        "id": assignment_id,
    }) == 0
    assert session.scalar(text("SELECT count(*) FROM audit_logs WHERE resource_id = :id AND action = 'DOCUMENT_DELETED'"), {
        "id": ids["owned"],
    }) == 1
    assert client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key, user_id=43)).status_code == 404


def test_delete_preserves_files_referenced_through_legacy_aliases(client, records, signing_key, tmp_path):
    session, ids, _, _ = records
    path = tmp_path / "synthetic.txt"
    session.execute(text("UPDATE documents SET storage_path = :path WHERE document_id = :id"), {
        "id": ids["owned"], "path": path.as_uri(),
    })
    response = client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key))
    assert response.status_code == 200
    assert response.json()["file_deleted"] is False
    assert path.read_text() == "Synthetic document"
    assert client.get(f"/api/v1/documents/{ids['legacy']}/preview", headers=authorization(signing_key)).status_code == 200


@pytest.mark.parametrize("link_type", ["symbolic", "hard"])
def test_shared_file_is_cleaned_after_last_reference(client, records, signing_key, deletable_file, tmp_path, link_type):
    session, ids, _, _ = records
    alias = tmp_path / "live-alias.txt"
    if link_type == "symbolic":
        alias.symlink_to(deletable_file)
    else:
        alias.hardlink_to(deletable_file)
    session.execute(text("UPDATE documents SET storage_path = :path WHERE document_id = :id"), {
        "id": ids["legacy"], "path": str(alias),
    })
    headers = authorization(signing_key)
    assert client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers).json()["file_deleted"] is False
    assert client.get(f"/api/v1/documents/{ids['legacy']}/preview", headers=headers).status_code == 200
    assert deletable_file.exists()
    assert client.delete(f"/api/v1/documents/{ids['legacy']}", headers=headers).json()["file_deleted"] is True
    assert client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers).json()["file_deleted"] is True
    assert not deletable_file.exists()
    assert not alias.exists()


def test_delete_unlinks_a_symlink_without_removing_its_target(client, records, signing_key, tmp_path):
    session, ids, _, _ = records
    target = tmp_path.parent / f"{uuid4().hex}-outside.txt"
    target.write_text("Synthetic external target", encoding="utf-8")
    link = tmp_path / "document-link"
    link.symlink_to(target)
    try:
        session.execute(text("UPDATE documents SET storage_path = :path WHERE document_id = :id"), {
            "id": ids["owned"], "path": str(link),
        })
        response = client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key))
        assert response.status_code == 200
        assert response.json()["file_deleted"] is True
        assert not link.is_symlink()
        assert target.read_text() == "Synthetic external target"
    finally:
        target.unlink(missing_ok=True)


def test_filesystem_failure_is_durable_and_retryable(client, records, signing_key, deletable_file, monkeypatch):
    session, ids, _, _ = records
    original_unlink = Path.unlink

    def denied_unlink(path, *args, **kwargs):
        if path == deletable_file:
            raise PermissionError("Synthetic filesystem failure")
        return original_unlink(path, *args, **kwargs)

    headers = authorization(signing_key)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", denied_unlink)
        response = client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["file_deleted"] is False
    assert deletable_file.exists()
    pending = session.execute(text("SELECT completed_at, attempts, last_error FROM document_deletions WHERE document_id = :id"), {
        "id": ids["owned"],
    }).one()
    assert pending.completed_at is None
    assert pending.attempts == 1
    assert pending.last_error == "PermissionError"
    assert client.get(f"/api/v1/documents/{ids['owned']}/preview", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{ids['owned']}", headers=headers).json()["file_deleted"] is True
    assert not deletable_file.exists()


def test_database_failure_leaves_original_file_and_document(client, records, signing_key, deletable_file, monkeypatch):
    session, ids, _, _ = records
    session.commit()

    def failed_commit():
        raise RuntimeError("Synthetic commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(session, "commit", failed_commit)
        with pytest.raises(RuntimeError, match="Synthetic commit failure"):
            client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key))
    session.rollback()
    assert deletable_file.exists()
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id = :id"), {"id": ids["owned"]}) == 1
    assert session.scalar(text("SELECT count(*) FROM document_deletions WHERE document_id = :id"), {"id": ids["owned"]}) == 0


def test_completion_failure_recovers_after_file_removal(client, records, signing_key, deletable_file, monkeypatch):
    session, ids, _, _ = records

    def failed_completion(*args):
        raise RuntimeError("Synthetic completion failure")

    with monkeypatch.context() as patch:
        patch.setattr(DocumentAccessRepositoryPg, "complete_deletion", failed_completion)
        with pytest.raises(RuntimeError, match="Synthetic completion failure"):
            client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key))
    session.rollback()
    assert not deletable_file.exists()
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id = :id"), {"id": ids["owned"]}) == 0
    assert session.scalar(text("SELECT count(*) FROM document_deletions WHERE document_id = :id AND completed_at IS NULL"), {
        "id": ids["owned"],
    }) == 1
    response = client.delete(f"/api/v1/documents/{ids['owned']}", headers=authorization(signing_key))
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["file_deleted"] is False


def test_delete_legacy_owner_with_orphaned_tenant_metadata(client, records, signing_key):
    session, ids, _, _ = records
    session.execute(text("""
        UPDATE documents SET tenant_id = NULL, metadata = jsonb_build_object('owner_user_id', 42, 'tenant_id', 'orphan')
        WHERE document_id = :id
    """), {"id": ids["legacy"]})
    assert client.delete(f"/api/v1/documents/{ids['legacy']}", headers=authorization(signing_key)).status_code == 200
