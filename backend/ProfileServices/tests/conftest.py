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


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def settings(tmp_path, signing_key):
    key_path = tmp_path / "public.pem"
    key_path.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    return Settings(
        database_url=os.environ["PROFILE_TEST_DATABASE_URL"],
        auth_jwt_public_key_path=key_path, profile_uploads_dir=tmp_path / "avatars",
        db_pool_min_size=1, db_pool_max_size=2, db_timeout_seconds=1,
    )


@pytest.fixture
def profile_id():
    return "profile002-" + uuid4().hex


@pytest.fixture
def token_headers(signing_key, profile_id):
    def make_headers(**claims):
        payload = {"user_id": profile_id, "token_type": "access", "exp": int(time()) + 300}
        payload.update(claims)
        return {"Authorization": "Bearer " + jwt.encode(payload, signing_key, algorithm="RS256")}
    return make_headers


@pytest.fixture
def db_session(settings, profile_id):
    # Explicit opt-in URL, existing schema only. Even route-level commit stays in the savepoint.
    engine = create_engine(settings.database_url, hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM user_profiles WHERE user_id=:id"),
                                     {"id": profile_id}) == 0
    finally:
        engine.dispose()


@pytest.fixture
def client(settings, db_session):
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as configured:
        yield configured
    assert app.state.database._engine is None
