import os
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config.settings import get_settings
from app.main import app


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def configured_client(tmp_path, signing_key):
    path = tmp_path / "public.pem"
    path.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    settings = get_settings().model_copy(update={"auth_jwt_public_key_path": str(path)})
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, settings
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def engine():
    # Explicit opt-in to a development database; never create or migrate shared tables.
    configured = create_engine(os.environ["TRANSFER_TEST_DATABASE_URL"])
    try:
        yield configured
    finally:
        configured.dispose()


@pytest.fixture
def runtime_engine():
    configured = create_engine(get_settings().database_url)
    try:
        with configured.connect() as connection:
            assert connection.scalar(text("SELECT session_user")) == "document_transfer_runtime"
        yield configured
    finally:
        configured.dispose()


@pytest.fixture
def committed_records(engine):
    document, transfer = uuid4().hex, uuid4().hex
    owner = int(uuid4().hex[:12], 16)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO documents (document_id, owner_user_id, filename, storage_path, mime_type)
            VALUES (:id, :owner, 'synthetic.txt', 'synthetic.txt', 'text/plain')
        """), {"id": document, "owner": str(owner)})
        connection.execute(text("""
            INSERT INTO transfer_events (transfer_id, owner_user_id, filename, direction, status)
            VALUES (:id, :owner, 'synthetic.txt', 'UPLOAD', 'PENDING')
        """), {"id": transfer, "owner": str(owner)})
    try:
        yield document, transfer, owner
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)})
            connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0
            assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": document}) == 0
