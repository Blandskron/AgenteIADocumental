import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError

from app.config.settings import Settings, get_settings
from app.infrastructure.database.connection import Database
from app.main import app, database, lifespan


def test_service_env_is_local_and_environment_has_precedence(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('APP_NAME=synthetic-root\nCORS_ORIGINS=["https://synthetic-root.example"]\n', encoding="utf-8")
    directory = tmp_path / "backend" / "library"
    directory.mkdir(parents=True)
    monkeypatch.chdir(directory)
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings()
    assert settings.app_name == "document-library-service"
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    (directory / ".env").write_text('APP_NAME=synthetic-local\nCORS_ORIGINS=["https://synthetic-local.example"]\n', encoding="utf-8")
    assert Settings().app_name == "synthetic-local"
    assert Settings().cors_origins == ["https://synthetic-local.example"]
    monkeypatch.setenv("APP_NAME", "synthetic-environment")
    assert Settings().app_name == "synthetic-environment"


@pytest.mark.parametrize("options", [
    {"db_pool_min_size": 0}, {"db_pool_max_size": 101}, {"db_pool_min_size": 5, "db_pool_max_size": 2},
    {"db_timeout_seconds": 0}, {"db_timeout_seconds": 301},
])
def test_invalid_connection_settings_fail_before_startup(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **options)


def test_pool_capacity_times_out_and_recovers():
    configured = Database(get_settings().database_url, pool_min_size=1, pool_max_size=2, timeout_seconds=1)
    try:
        with configured.session() as first, configured.session() as second:
            first.execute(text("SELECT 1"))
            second.execute(text("SELECT 1"))
            with configured.session() as third:
                with pytest.raises(TimeoutError):
                    third.execute(text("SELECT 1"))
        with configured.session() as recovered:
            assert recovered.scalar(text("SELECT 1")) == 1
            parameters = recovered.connection().connection.driver_connection.info.get_parameters()
            assert parameters["connect_timeout"] == "1"
    finally:
        configured.close()


def test_session_exception_rolls_back_uncommitted_work():
    configured = Database(get_settings().database_url, pool_min_size=1, pool_max_size=1)
    try:
        with configured.session() as session:
            session.execute(text("CREATE TEMP TABLE library_transaction_probe (id integer)"))
            session.commit()
        with pytest.raises(RuntimeError):
            with configured.session() as session:
                session.execute(text("INSERT INTO library_transaction_probe VALUES (1)"))
                raise RuntimeError("Synthetic interruption")
        with configured.session() as session:
            assert session.scalar(text("SELECT count(*) FROM library_transaction_probe")) == 0
    finally:
        configured.close()


def test_lifespan_closes_connections_after_exception():
    async def exercise():
        with pytest.raises(RuntimeError, match="Synthetic lifespan interruption"):
            async with lifespan(app):
                with database.session() as session:
                    assert session.scalar(text("SELECT 1")) == 1
                raise RuntimeError("Synthetic lifespan interruption")
        assert database._engine is None
        assert database._session_factory is None

    asyncio.run(exercise())


def test_database_can_reopen_after_shutdown():
    configured = Database(get_settings().database_url)
    try:
        for _ in range(2):
            with configured.session() as session:
                assert session.scalar(text("SELECT 1")) == 1
            configured.close()
    finally:
        configured.close()
