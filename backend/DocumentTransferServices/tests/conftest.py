import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

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
