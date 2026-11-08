import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, TimeoutError

from app.config.database import get_session
from app.infrastructure.database.connection import Database
from app.main import create_app

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("dependency", ["key", "db", "storage"])
def test_readiness_loss_is_sanitized(settings, dependency, monkeypatch):
    app = create_app(settings)
    unavailable = Database("postgresql+psycopg://synthetic:private@127.0.0.1:1/db", timeout_seconds=1)
    try:
        with TestClient(app) as client:
            if dependency == "key":
                settings.auth_jwt_public_key_path.write_bytes(b"private-value")
            elif dependency == "db":
                def failed_session():
                    with unavailable.session() as session:
                        yield session
                app.dependency_overrides[get_session] = failed_session
            else:
                def fail(**kwargs): raise PermissionError("private-storage")
                monkeypatch.setattr("app.config.readiness.TemporaryFile", fail)
            response = client.get("/api/v1/health/db")
            assert response.status_code == 503
            assert response.json() == {"detail": "Export dependencies are unavailable."}
            assert client.get("/api/v1/health").status_code == 200
    finally:
        unavailable.close()
    assert app.state.database._engine is None


def test_real_pool_timeout_and_failed_transaction_recovery(settings):
    if "127.0.0.1:1/" in settings.database_url:
        pytest.fail("Explicit EXPORT_TEST_DATABASE_URL is required")
    database = Database(settings.database_url, 1, 1, 1)
    database.open()
    try:
        with database.session() as first:
            assert first.scalar(text("SELECT 1")) == 1
            with pytest.raises(TimeoutError):
                with database.session() as second:
                    second.scalar(text("SELECT 1"))
        with pytest.raises(DBAPIError):
            with database.session() as session:
                session.execute(text("SELECT 1/0"))
        with database.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
            assert session.scalar(text("SHOW statement_timeout")) == "1s"
    finally:
        database.close()


def test_real_statement_timeout(settings):
    database = Database(settings.database_url, 1, 1, 1)
    try:
        with pytest.raises(DBAPIError):
            with database.session() as session:
                session.execute(text("SELECT pg_sleep(2)"))
        with database.session() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        database.close()
