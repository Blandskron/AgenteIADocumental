import importlib

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


@pytest.mark.parametrize(("field", "value"), [
    ("db_pool_min_size", 0), ("db_pool_max_size", 101), ("db_pool_min_size", 3),
    ("db_timeout_seconds", 0), ("db_timeout_seconds", 301),
    ("auth_jwt_algorithm", "HS256"), ("log_level", "INVALID"),
    ("database_url", "sqlite:///local.db"), ("database_url", "postgresql://user@host/db"),
    ("database_url", "postgresql+psycopg://user@host"),
    ("database_url", "synthetic-secret"),
    ("auth_jwt_public_key_path", "relative.pem"),
    ("export_storage_base_path", "relative-exports"),
    ("cors_origins", ["*"]), ("cors_origins", ["https://*.example.invalid"]),
    ("cors_origins", ["https://user:pass@example.invalid"]),
    ("cors_origins", ["https://example.invalid/path"]),
    ("cors_origins", ["https://example.invalid#fragment"]),
    ("cors_origins", ["https://example.invalid?query=1"]),
    ("cors_origins", ["ftp://example.invalid"]),
    ("cors_origins", ["https://example.invalid:invalid"]),
    ("cors_origins", ["https://example.invalid:0"]),
    ("cors_origins", ["https://example .invalid"]),
])
def test_invalid_configuration(settings, field, value):
    data = settings.model_dump()
    data[field] = value
    with pytest.raises(ValidationError) as caught:
        Settings(**data)
    assert "synthetic-secret" not in str(caught.value)


def test_no_implicit_dotenv_or_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("EXPORT_STORAGE_BASE_PATH", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql+psycopg://user:synthetic-secret@host/db\n")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert {error["loc"][0] for error in caught.value.errors()} >= {
        "database_url", "auth_jwt_public_key_path", "export_storage_base_path",
    }
    assert "synthetic-secret" not in str(caught.value)


def test_origins_and_repr(settings):
    data = settings.model_dump()
    data["cors_origins"] = ["https://example.invalid", "https://example.invalid", "http://localhost:3000"]
    configured = Settings(**data)
    assert configured.cors_origins == ["https://example.invalid", "http://localhost:3000"]
    assert "database_url" not in repr(configured)
    assert Settings(**{**data, "cors_origins": []}).cors_origins == []


def test_import_and_factory_have_no_filesystem_effect(settings):
    module = importlib.import_module("app.main")
    module = importlib.reload(module)
    app = module.create_app(settings)
    assert app.state.database._engine is None
    assert not settings.export_storage_base_path.exists()
