from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.security import require_authenticated_user, require_upload_user
from app.config.settings import Settings, get_settings
from app.domain.documents.exceptions import DocumentNotFoundError
from app.infrastructure.database.repositories.document_reader_pg import DocumentReaderPg
from app.infrastructure.database.repositories.document_writer_pg import DocumentWriterPg
from app.interfaces.api.v1.routes.document_routes import document_status, process_document, upload_document


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.parametrize("claims", [
    {"exp": 4102444800}, {"user_id": 42}, {"user_id": True, "exp": 4102444800},
    {"user_id": "42", "exp": 4102444800}, {"user_id": 42, "exp": 0},
    {"user_id": 42, "exp": []}, {"user_id": 42, "exp": 4102444800, "token_type": "refresh"},
])
def test_rejects_invalid_jwt(signing_key, tmp_path, claims):
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    token = jwt.encode({"token_type": "access", "sub": "42", **claims}, signing_key, algorithm="RS256")
    with pytest.raises(HTTPException) as error:
        require_authenticated_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            Settings(auth_jwt_public_key_path=str(public_key)),
        )
    assert error.value.status_code == 401


def test_upload_requires_permission_and_uses_claims_for_ownership():
    with pytest.raises(HTTPException) as error:
        require_upload_user({"user_id": 42})
    assert error.value.status_code == 403
    uploader = require_upload_user({"user_id": 42, "active_permissions": ["upload_documents"]})
    use_case = Mock()
    use_case.execute.return_value = SimpleNamespace(
        document_id="synthetic", filename="fixture.txt", status=SimpleNamespace(value="PENDING"),
        mime_type="text/plain", storage_path="fixture.txt", metadata={},
    )
    upload_document(
        SimpleNamespace(filename="fixture.txt", content_type="text/plain", file=object()),
        '{"owner_user_id":"999","tenant_id":"foreign","owner_groups":["foreign"],"source":"google_drive"}',
        False, uploader, use_case,
    )
    metadata = use_case.execute.call_args.kwargs["metadata"]
    assert metadata["owner_user_id"] == "42"
    assert metadata["tenant_id"] is None
    assert metadata["owner_groups"] == []
    assert metadata["source"] == "google_drive"


def test_read_and_mutation_scopes_with_postgres():
    engine = create_engine(get_settings().database_url)
    tenant, document = uuid4().hex, uuid4().hex
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic')"), {"id": tenant})
            session.execute(text("""
                INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, metadata)
                VALUES (:document, :tenant, '42', 'fixture.txt', 'fixture.txt', 'text/plain',
                        '{"owner_user_id":"43","owner_groups":["readers"]}')
            """), {"document": document, "tenant": tenant})
            reader = DocumentReaderPg(session)
            ingest = Mock()
            group_member = {"user_id": 44, "groups": ["readers"], "tenant_memberships": [{"tenant_id": tenant}]}
            assert document_status(document, group_member, reader).status == "PENDING"
            with pytest.raises(DocumentNotFoundError):
                process_document(document, group_member, reader, ingest)
            ingest.execute.assert_not_called()
            for outsider in ({"user_id": 43}, {"user_id": 45, "groups": ["readers"]}, {
                "user_id": 46, "active_tenant_id": "foreign", "active_permissions": ["manage_documents"],
            }):
                with pytest.raises(DocumentNotFoundError):
                    document_status(document, outsider, reader)
                with pytest.raises(DocumentNotFoundError):
                    process_document(document, outsider, reader, ingest)
            for manager in (
                {"user_id": 42},
                {"user_id": 47, "tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}]},
                {"user_id": 48, "active_tenant_id": tenant, "active_permissions": ["manage_documents"]},
            ):
                assert process_document(document, manager, reader, ingest).status == "PROCESSED"
            assert ingest.execute.call_count == 3
    finally:
        engine.dispose()


def test_writer_returns_registered_document_with_database_generated_id():
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                document = DocumentWriterPg(session).create(
                    "fixture.txt", "fixture.txt", "text/plain", {"owner_user_id": "42"},
                )
                assert document.document_id
                assert document.owner_user_id == "42"
                assert DocumentReaderPg(session).get_by_id(document.document_id) == document
            transaction.rollback()
    finally:
        engine.dispose()
