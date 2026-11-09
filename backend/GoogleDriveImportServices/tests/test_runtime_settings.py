import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings
from app.infrastructure.google.token_cipher import TokenCipher
from app.main import create_app


@pytest.mark.parametrize("values",[
    {"database_url":"sqlite:///private"},{"auth_jwt_public_key_path":"relative.pem"},
    {"auth_jwt_algorithm":"HS256"},{"cors_origins":["*"]},{"cors_origins":["http://user:secret@localhost"]},
    {"db_pool_min_size":10,"db_pool_max_size":1},{"db_timeout_seconds":0},
    {"google_oauth_token_url":"http://evil.test/token"},{"rag_document_base_url":"http://evil.test"},
    {"google_oauth_scopes":"https://www.googleapis.com/auth/drive"},
    {"google_drive_enabled":True},{"google_drive_enabled":True,"google_oauth_client_id":"id","google_oauth_client_secret":"secret","google_token_encryption_key":"change-me-with-a-long-random-secret"}])
def test_configuration_fails_closed(settings, values):
    data=settings.model_dump()
    data.update(values)
    with pytest.raises(ValidationError):
        Settings(**data)


def test_disabled_and_enabled_configuration_and_secret_repr(settings):
    assert settings.google_drive_enabled is False
    data=settings.model_dump()
    data.update(google_drive_enabled=True,google_oauth_client_id="synthetic-id",
                google_oauth_client_secret="synthetic-private-secret",google_token_encryption_key="a"*48)
    configured=Settings(**data)
    assert configured.google_oauth_scope_list==["https://www.googleapis.com/auth/drive.file"]
    assert "synthetic-private-secret" not in repr(configured)
    assert "a"*48 not in repr(configured)
    assert TokenCipher("a"*48).decrypt(TokenCipher("a"*48).encrypt("synthetic"))=="synthetic"


@pytest.mark.parametrize("secret",["","short","change-me-with-a-long-random-secret","local-google-drive-import-development-secret"])
def test_no_encryption_fallback(secret):
    with pytest.raises(ValueError):
        TokenCipher(secret)


def test_import_does_not_construct_app_or_read_dotenv(monkeypatch):
    monkeypatch.delenv("DATABASE_URL",raising=False)
    monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY_PATH",raising=False)
    sys.modules.pop("app.main",None)
    module=importlib.import_module("app.main")
    assert not hasattr(module,"app")


def test_startup_failure_closes_engine_and_hides_configuration(settings):
    app=create_app(settings)
    with pytest.raises(RuntimeError,match="Drive dependencies are unavailable"):
        with TestClient(app):
            pass
    assert app.state.database._engine is None


def test_schema_generation_without_lifespan(settings):
    schema=create_app(settings).openapi()
    assert len(schema["paths"])==9
