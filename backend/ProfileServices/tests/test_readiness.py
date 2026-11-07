import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config.database import get_session
from app.infrastructure.database.connection import Database
from app.main import create_app


def test_startup_health_and_shutdown(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/v1/health/db").json() == {"status": "ok"}
        with app.state.database.session() as session:
            assert session.scalar(text("SHOW statement_timeout")) == "1s"
            assert session.scalar(text("SELECT 1")) == 1
    assert app.state.database._engine is None
    assert app.state.database._session_factory is None


@pytest.mark.parametrize("kind", ["missing", "invalid", "private", "ec", "weak"])
def test_invalid_key_fails_startup_without_details(settings, signing_key, kind):
    path = settings.auth_jwt_public_key_path
    if kind == "missing":
        path.unlink()
    elif kind == "invalid":
        path.write_bytes(b"synthetic-secret")
    elif kind == "private":
        path.write_bytes(signing_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ))
    else:
        key = (ec.generate_private_key(ec.SECP256R1()) if kind == "ec"
               else rsa.generate_private_key(public_exponent=65537, key_size=1024))
        path.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="^Profile dependencies are unavailable.$"):
        with TestClient(app):
            pass
    assert app.state.database._engine is None
    assert app.state.database._session_factory is None


def test_database_unavailable_fails_startup(settings):
    settings = settings.model_copy(update={"database_url": "postgresql+psycopg://user:synthetic-secret@127.0.0.1:1/db"})
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="^Profile dependencies are unavailable.$"):
        with TestClient(app):
            pass
    assert app.state.database._engine is None


@pytest.mark.parametrize("dependency", ["key", "database"])
def test_readiness_after_dependency_loss(settings, dependency):
    app = create_app(settings)
    unavailable = Database("postgresql+psycopg://user:synthetic-secret@127.0.0.1:1/db", timeout_seconds=1)
    try:
        with TestClient(app) as client:
            if dependency == "key":
                settings.auth_jwt_public_key_path.write_bytes(b"synthetic-secret")
            else:
                def failed_session():
                    with unavailable.session() as session:
                        yield session
                app.dependency_overrides[get_session] = failed_session
            response = client.get("/api/v1/health/db")
            assert response.status_code == 503
            assert response.json() == {"detail": "Profile dependencies are unavailable."}
            assert client.get("/api/v1/health").status_code == 200
    finally:
        unavailable.close()


def test_pool_exhaustion_and_session_rollback(settings):
    from sqlalchemy.exc import TimeoutError

    database = Database(settings.database_url, 1, 1, 1)
    database.open()
    try:
        with database.session() as first:
            assert first.scalar(text("SELECT 1")) == 1
            with pytest.raises(TimeoutError):
                with database.session() as second:
                    second.scalar(text("SELECT 1"))
        # The first lease returns to the pool; an exception rolls back its transaction.
        with pytest.raises(RuntimeError, match="synthetic"):
            with database.session() as session:
                session.execute(text("SELECT 1"))
                raise RuntimeError("synthetic")
        with database.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        database.close()


def test_statement_timeout_cancels_and_releases_connection(settings):
    from sqlalchemy.exc import DBAPIError

    database = Database(settings.database_url, 1, 1, 1)
    try:
        with pytest.raises(DBAPIError) as caught:
            with database.session() as session:
                session.execute(text("SELECT pg_sleep(2)"))
        assert caught.value.orig.sqlstate == "57014"
        with database.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        database.close()


def test_lifespan_exception_still_closes_engine(settings):
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="synthetic"):
        with TestClient(app):
            raise RuntimeError("synthetic")
    assert app.state.database._engine is None
    assert app.state.database._session_factory is None


def test_readiness_missing_table_is_sanitized(client, db_session):
    db_session.execute(text("SET LOCAL search_path TO pg_temp"))
    response = client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Profile dependencies are unavailable."}
