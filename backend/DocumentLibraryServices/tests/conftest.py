import jwt as identity_fixture_jwt
import pytest as identity_fixture_pytest
import re
from os import environ
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from database_support import SQL_ROOT, execute_script, migrate

from app.config.settings import get_settings
from app.main import app


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def configured_client(tmp_path, monkeypatch, signing_key):
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    settings = get_settings().model_copy(update={"auth_jwt_public_key_path": str(public_key)})
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)
    with TestClient(app) as client:
        yield client, settings


@pytest.fixture
def legacy_database():
    name = f"lib004_{uuid4().hex}"
    admin_url = make_url(environ["LIBRARY_TEST_DATABASE_URL"])
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    engine, created = None, False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True
        engine = create_engine(admin_url.set(database=name))
        with engine.connect() as connection:
            execute_script(connection, SQL_ROOT / "run_all.sql", legacy=True)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            assert re.fullmatch(r"lib004_[0-9a-f]{32}", name)
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def migrated_database(legacy_database):
    migrate(legacy_database)
    with legacy_database.begin() as connection:
        execute_script(connection, SQL_ROOT / "library/permissions.sql")
        execute_script(connection, SQL_ROOT / "library/verify_role.sql")
    return legacy_database


# Existing isolated API/SQL tests use synthetic signers rather than the live Auth service.
# test_current_identity exercises the actual transport; release demo uses real Auth.


@identity_fixture_pytest.fixture(autouse=True)
def isolated_identity_provider(monkeypatch):
    def current(token, identifier, url):
        payload = identity_fixture_jwt.decode(token, options={"verify_signature": False})
        return {"id": identifier, "groups": payload.get("groups", []), "permissions": payload.get("permissions", []), **payload}
    monkeypatch.setattr("app.config.security.load_current_profile", current)
