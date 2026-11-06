import os
import hashlib
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
    return str(1_000_000_000 + int(uuid4().hex[:7], 16))


@pytest.fixture
def encoded_password():
    return "pbkdf2_sha256$1000000$profile003$synthetic"


@pytest.fixture
def token_headers(signing_key, profile_id, encoded_password):
    def make_headers(**claims):
        payload = {"user_id": int(profile_id), "token_type": "access", "exp": int(time()) + 300,
                   "iat": int(time()), "jti": uuid4().hex,
                   "hash_password": hashlib.md5(encoded_password.encode()).hexdigest().upper()}
        payload.update(claims)
        return {"Authorization": "Bearer " + jwt.encode(payload, signing_key, algorithm="RS256")}
    return make_headers


@pytest.fixture
def db_session(settings, profile_id, encoded_password):
    # Explicit opt-in URL, existing schema only. Even route-level commit stays in the savepoint.
    engine = create_engine(settings.database_url, hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        identifiers = [int(profile_id)]
        session.info["synthetic_ids"] = identifiers
        try:
            insert_user(session, int(profile_id), encoded_password)
            yield session
        finally:
            session.close()
            transaction.rollback()
    try:
        with engine.connect() as connection:
            for identifier in identifiers:
                assert connection.scalar(text("SELECT count(*) FROM user_profiles WHERE user_id=:id"),
                                         {"id": str(identifier)}) == 0
                assert connection.scalar(text("SELECT count(*) FROM auth_user WHERE id=:id"),
                                         {"id": identifier}) == 0
    finally:
        engine.dispose()


def insert_user(session, identifier, password):
    session.execute(text("""
        INSERT INTO auth_user (id, password, is_superuser, username, first_name, last_name,
                               email, is_staff, is_active, date_joined)
        VALUES (:id, :password, FALSE, :username, '', '', '', FALSE, TRUE, NOW())
    """), {"id": identifier, "password": password, "username": "profile003-" + uuid4().hex})


@pytest.fixture
def other_id(db_session, encoded_password):
    identifier = 1_500_000_000 + int(uuid4().hex[:7], 16)
    insert_user(db_session, identifier, encoded_password)
    db_session.info["synthetic_ids"].append(identifier)
    return str(identifier)


@pytest.fixture
def client(settings, db_session):
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as configured:
        yield configured
    assert app.state.database._engine is None
