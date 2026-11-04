from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.application.documents.use_cases.build_chat_context import BuildChatContext
from app.application.documents.use_cases.get_document_chunks import GetDocumentChunks
from app.application.documents.use_cases.get_document_detail import GetDocumentDetail
from app.config.security import require_authenticated_user
from app.config.settings import Settings, get_settings
from app.domain.documents import DocumentNotFoundError, InvalidDocumentSelectionError
from app.infrastructure.database.repositories.document_search_repository_pg import DocumentSearchRepositoryPg


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.parametrize("claims", [
    {"exp": 4102444800},
    {"user_id": 42},
    {"user_id": True, "exp": 4102444800},
    {"user_id": "42", "exp": 4102444800},
    {"user_id": 0, "exp": 4102444800},
    {"user_id": 42, "exp": 0},
    {"user_id": 42, "exp": []},
    {"user_id": 42, "exp": 4102444800, "token_type": "refresh"},
])
def test_rejects_invalid_jwt(signing_key, tmp_path, claims):
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    token = jwt.encode({"token_type": "access", "sub": "42", "username": "42", **claims}, signing_key, algorithm="RS256")
    with pytest.raises(HTTPException) as error:
        require_authenticated_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            Settings(auth_jwt_public_key_path=str(public_key)),
        )
    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.fixture
def records():
    engine = create_engine(get_settings().database_url)
    marker = uuid4().hex
    tenant, foreign_tenant = uuid4().hex, uuid4().hex
    ids = {kind: uuid4().hex for kind in ("owned", "legacy", "group", "assigned", "managed", "foreign")}
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic')"), [
                {"id": tenant}, {"id": foreign_tenant},
            ])
            session.execute(text("""
                INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, status, metadata)
                VALUES (:id, :tenant, :owner, :filename, 'fixture.txt', 'text/plain', 'PROCESSED', CAST(:metadata AS jsonb))
            """), [
                {"id": document, "tenant": foreign_tenant if kind == "foreign" else tenant,
                 "owner": "42" if kind == "owned" else None if kind == "legacy" else "43",
                 "filename": f"{marker}-{kind}.txt", "metadata": {
                     "owned": '{"owner_user_id":"43"}',
                     "legacy": '{"owner_user_id":"42"}',
                     "group": '{"owner_groups":["readers"]}',
                     "foreign": f'{{"owner_groups":["readers"],"tenant_id":"{tenant}"}}',
                 }.get(kind, "{}")}
                for kind, document in ids.items()
            ])
            session.execute(text("""
                INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
                VALUES (:id, 0, :content, array_fill(1.0::real, ARRAY[384])::vector)
            """), [{"id": document, "content": f"Synthetic fragment {marker}"} for document in ids.values()])
            session.execute(text("""
                INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id)
                VALUES (:id, :tenant, :recipient, :sender)
            """), [
                {"id": ids["assigned"], "tenant": tenant, "recipient": "42", "sender": "43"},
                {"id": ids["managed"], "tenant": tenant, "recipient": "43", "sender": "42"},
            ])
            yield session, ids, tenant, marker
    finally:
        engine.dispose()


def test_permissions_apply_to_all_search_surfaces(records):
    session, ids, tenant, marker = records
    actor = {"user_id": 42, "groups": ["readers"], "tenant_memberships": [{"tenant_id": tenant}]}
    repository = DocumentSearchRepositoryPg(session, actor)
    page = repository.search(query=marker)
    allowed = {ids[kind] for kind in ("owned", "legacy", "group", "assigned", "managed")}
    assert page.total == len(allowed)
    assert {item.document_id for item in page.items} == allowed
    assert all(item.chunk_count == 1 and marker in item.snippet for item in page.items)
    assert GetDocumentDetail(repository).execute(ids["legacy"]).document_id == ids["legacy"]
    assert GetDocumentChunks(repository).execute(ids["group"])[1] == 1
    selection = BuildChatContext(repository).execute([ids["assigned"], ids["owned"]])
    assert [item.document_id for item in selection.documents] == [ids["assigned"], ids["owned"]]

    for document_id in (ids["foreign"], "missing"):
        with pytest.raises(DocumentNotFoundError):
            GetDocumentDetail(repository).execute(document_id)
        with pytest.raises(DocumentNotFoundError):
            GetDocumentChunks(repository).execute(document_id)
        with pytest.raises(InvalidDocumentSelectionError):
            BuildChatContext(repository).execute([ids["owned"], document_id])

    assert DocumentSearchRepositoryPg(session, {"user_id": 43}).get_by_id(ids["owned"]) is None
    tenant_admin = DocumentSearchRepositoryPg(session, {
        "user_id": 44, "tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}],
    })
    assert tenant_admin.get_by_id(ids["group"]) is not None
    assert tenant_admin.get_by_id(ids["foreign"]) is None


def test_revocation_removes_assignment_access_for_sender_and_recipient(records):
    session, ids, _, marker = records
    repository = DocumentSearchRepositoryPg(session, {"user_id": 42})
    session.execute(text("UPDATE document_assignments SET status = 'CANCELLED' WHERE document_id = :id"), {"id": ids["assigned"]})
    session.execute(text("UPDATE document_assignments SET status = 'EXPIRED' WHERE document_id = :id"), {"id": ids["managed"]})
    page = repository.search(query=marker)
    assert page.total == 2
    assert {item.document_id for item in page.items} == {ids["owned"], ids["legacy"]}
    for kind in ("assigned", "managed"):
        assert repository.get_by_id(ids[kind]) is None
        assert repository.get_chunks(ids[kind]) == ([], 0)
        assert repository.get_many_by_ids([ids[kind]]) == []
