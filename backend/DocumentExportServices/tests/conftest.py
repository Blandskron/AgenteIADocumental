import os
from time import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def require_explicit_postgres(request):
    if request.node.get_closest_marker("postgres") and not os.environ.get("EXPORT_TEST_DATABASE_URL"):
        pytest.fail("PostgreSQL tests require explicit EXPORT_TEST_DATABASE_URL and synthetic schema.")


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def owner():
    return str(1_000_000_000 + int(uuid4().hex[:7], 16))


@pytest.fixture
def settings(tmp_path, signing_key):
    key = tmp_path / "public.pem"
    key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return Settings(database_url=os.environ.get("EXPORT_TEST_DATABASE_URL", "postgresql+psycopg://synthetic@127.0.0.1:1/test"),
                    auth_jwt_public_key_path=key, export_storage_base_path=tmp_path / "exports",
                    db_pool_min_size=1, db_pool_max_size=2, db_timeout_seconds=1)


@pytest.fixture
def token_headers(signing_key, owner):
    def make(**changes):
        payload = {"user_id": int(owner), "token_type": "access", "exp": int(time()) + 300,
                   "iat": int(time()), "jti": uuid4().hex, "hash_password": "A" * 32}
        payload.update(changes)
        return {"Authorization": "Bearer " + jwt.encode(payload, signing_key, algorithm="RS256")}
    return make


@pytest.fixture
def db_session(settings, owner):
    if not os.environ.get("EXPORT_TEST_DATABASE_URL"):
        pytest.fail("PostgreSQL tests require explicit EXPORT_TEST_DATABASE_URL and synthetic schema.")
    engine = create_engine(settings.database_url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 0
    finally:
        engine.dispose()


@pytest.fixture
def client(settings, db_session):
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client
    assert app.state.database._engine is None
