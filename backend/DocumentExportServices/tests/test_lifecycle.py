from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

from app.config.readiness import check_dependencies
from app.infrastructure.database.connection import Database
from app.main import create_app


@pytest.mark.parametrize("kind", ["missing", "invalid", "private", "ec", "weak"])
def test_key_rejected_without_internal_values(settings, signing_key, kind):
    path = settings.auth_jwt_public_key_path
    if kind == "missing":
        path.unlink()
    elif kind == "invalid":
        path.write_bytes(b"synthetic-private-detail")
    elif kind == "private":
        path.write_bytes(signing_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    else:
        key = ec.generate_private_key(ec.SECP256R1()) if kind == "ec" else rsa.generate_private_key(public_exponent=65537, key_size=1024)
        path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    with pytest.raises(RuntimeError, match="^Export verification key is unavailable or invalid.$"):
        check_dependencies(settings, Mock(), prepare=True)
    assert not settings.export_storage_base_path.exists()


def test_readiness_does_not_touch_legacy_storage(settings):
    session = Mock()
    check_dependencies(settings, session, prepare=True)
    session.scalar.assert_called_once()
    assert not settings.export_storage_base_path.exists()
    settings.export_storage_base_path.write_text("synthetic legacy obstruction")
    check_dependencies(settings, session)

def test_lifespan_failure_always_closes_and_masks(settings, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic-private-detail")
    monkeypatch.setattr("app.main.check_dependencies", fail)
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="^Export dependencies are unavailable.$"):
        with TestClient(app):
            pass
    assert app.state.database._engine is None
    assert app.state.database._session_factory is None


def test_shutdown_after_body_failure_closes(settings, monkeypatch):
    monkeypatch.setattr("app.main.check_dependencies", lambda *args, **kwargs: None)
    app = create_app(settings)
    with pytest.raises(RuntimeError, match="synthetic body"):
        with TestClient(app):
            raise RuntimeError("synthetic body")
    assert app.state.database._engine is None


def test_database_pool_configuration_without_open_connection(settings):
    database = Database(settings.database_url, 2, 4, 7)
    database.open()
    try:
        assert database._engine.pool.size() == 2
        assert database._engine.pool._max_overflow == 2
        assert database._engine.pool.timeout() == 7
        assert database._engine.hide_parameters is True
    finally:
        database.close()
