import asyncio
import os
from contextlib import nullcontext

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, TimeoutError

from app.config.settings import Settings
from app.infrastructure.database.connection import Database
from app.main import app, database, lifespan


def test_dotenv_files_are_not_loaded(tmp_path, monkeypatch):
    directory = tmp_path / "backend" / "transfer"
    directory.mkdir(parents=True)
    for path in (tmp_path / ".env", directory / ".env"):
        path.write_text('APP_NAME=synthetic-file\nCORS_ORIGINS=["*"]\nDB_POOL_MIN_SIZE=-1\n', encoding="utf-8")
    monkeypatch.chdir(directory)
    for name in ("APP_NAME", "CORS_ORIGINS", "DB_POOL_MIN_SIZE"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.app_name == "document-transfer-service"
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert settings.db_pool_min_size == 1
    monkeypatch.setenv("APP_NAME", "synthetic-environment")
    monkeypatch.setenv("CORS_ORIGINS", '["https://synthetic.example"]')
    assert Settings().app_name == "synthetic-environment"
    assert Settings().cors_origins == ["https://synthetic.example"]


@pytest.mark.parametrize("field,value", [
    ("db_pool_min_size", 0), ("db_pool_min_size", -1), ("db_pool_min_size", 101),
    ("db_pool_max_size", 0), ("db_pool_max_size", -1), ("db_pool_max_size", 101),
    ("db_timeout_seconds", 0), ("db_timeout_seconds", -1), ("db_timeout_seconds", 301),
    ("auth_jwt_algorithm", "HS256"),
])
def test_invalid_settings_fail_before_startup(field, value):
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_pool_relationship_and_valid_boundaries():
    with pytest.raises(ValidationError):
        Settings(db_pool_min_size=3, db_pool_max_size=2)
    assert Settings(db_pool_min_size=100, db_pool_max_size=100, db_timeout_seconds=300)
    assert Settings(db_pool_min_size=1, db_pool_max_size=1, db_timeout_seconds=1)


def test_pool_capacity_timeout_and_recovery():
    configured = Database(os.environ["TRANSFER_TEST_DATABASE_URL"], 1, 2, 1)
    try:
        with configured.session() as first, configured.session() as second:
            first.execute(text("SELECT 1"))
            second.execute(text("SELECT 1"))
            with configured.session() as third, pytest.raises(TimeoutError):
                third.execute(text("SELECT 1"))
        with configured.session() as recovered:
            assert recovered.scalar(text("SELECT 1")) == 1
            parameters = recovered.connection().connection.driver_connection.info.get_parameters()
            assert parameters["connect_timeout"] == "1"
        assert configured._engine.pool.size() == 1
    finally:
        configured.close()


def test_uncommitted_work_and_failed_session_are_rolled_back():
    configured = Database(os.environ["TRANSFER_TEST_DATABASE_URL"], 1, 1)
    try:
        with configured.session() as session:
            session.execute(text("CREATE TEMP TABLE transfer_transaction_probe (id integer)"))
            session.commit()
        with pytest.raises(DBAPIError):
            with configured.session() as session:
                session.execute(text("INSERT INTO transfer_transaction_probe VALUES (1)"))
                session.execute(text("SELECT 1 / 0"))
        with configured.session() as session:
            assert session.scalar(text("SELECT count(*) FROM transfer_transaction_probe")) == 0
    finally:
        configured.close()


@pytest.mark.parametrize("interrupt", [False, True])
def test_lifespan_closes_connections(interrupt):
    async def exercise():
        with pytest.raises(RuntimeError, match="Synthetic interruption") if interrupt else nullcontext():
            async with lifespan(app):
                with database.session() as session:
                    assert session.scalar(text("SELECT 1")) == 1
                if interrupt:
                    raise RuntimeError("Synthetic interruption")
        assert database._engine is None
        assert database._session_factory is None
    asyncio.run(exercise())


def test_lifespan_closes_after_open_failure(monkeypatch):
    called = []

    def fail():
        raise RuntimeError("Synthetic startup failure")

    monkeypatch.setattr(database, "open", fail)
    original_close = database.close

    def close():
        called.append(True)
        original_close()

    monkeypatch.setattr(database, "close", close)

    async def exercise():
        with pytest.raises(RuntimeError, match="Synthetic startup failure"):
            async with lifespan(app):
                pytest.fail("Startup unexpectedly succeeded")
    asyncio.run(exercise())
    assert called == [True]


def test_database_reopens_and_close_is_idempotent():
    configured = Database(os.environ["TRANSFER_TEST_DATABASE_URL"])
    try:
        for _ in range(2):
            with configured.session() as session:
                assert session.scalar(text("SELECT 1")) == 1
            configured.close()
            configured.close()
    finally:
        configured.close()
