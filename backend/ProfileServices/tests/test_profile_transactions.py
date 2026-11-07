from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.security import require_authenticated_user
from app.infrastructure.database.repositories.profile_repository_pg import UserProfileRepositoryPg
from app.main import create_app
from app.shared.errors import ConflictError



def wait_for_lock(engine, pid):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}) == "Lock":
                return
        sleep(0.01)
    raise AssertionError("Expected a real PostgreSQL lock wait")


@pytest.mark.parametrize("existing", [False, True])
def test_atomic_version_conflict_with_two_real_connections(committed_engine, profile_id, existing):
    engine = committed_engine
    if existing:
        with Session(engine, expire_on_commit=False) as seed:
            UserProfileRepositoryPg(seed, profile_id).create_or_update(0, {"email": "first@example.com"})
    expected = 1 if existing else 0
    started, pid = Event(), []
    with engine.connect() as first:
        transaction = first.begin()
        session = Session(bind=first, join_transaction_mode="create_savepoint", expire_on_commit=False)
        winner = UserProfileRepositoryPg(session, profile_id).create_or_update(expected, {"email": "winner@example.com"})

        def competing_write():
            with Session(engine, expire_on_commit=False) as second:
                pid.append(second.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                with pytest.raises(ConflictError):
                    UserProfileRepositoryPg(second, profile_id).create_or_update(expected, {"email": "loser@example.com"})

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(competing_write)
            try:
                assert started.wait(3)
                assert pid[0] != first.scalar(text("SELECT pg_backend_pid()"))
                wait_for_lock(engine, pid[0])
            finally:
                transaction.commit()
                session.close()
            future.result(timeout=5)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT email, version FROM user_profiles WHERE user_id=:id"), {"id": profile_id}).one()
        assert row.email == "winner@example.com" and row.version == winner.version


def test_parallel_http_create_and_update_preserve_winner(committed_engine, settings, token_headers):
    barrier = Barrier(2)
    def write(expected, label):
        with TestClient(create_app(settings)) as client:
            barrier.wait(timeout=5)
            response = client.put("/api/v1/profile", headers=token_headers(), json={
                "expected_version": expected, "additional_info": {"winner": label},
            })
            return response.status_code, response.json()
    for expected in (0, 1):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write, expected, label) for label in ("one", "two")]
            results = [future.result(timeout=10) for future in futures]
        assert sorted(status for status, _ in results) == [200, 409]
        saved = next(payload for status, payload in results if status == 200)
        with TestClient(create_app(settings)) as client:
            assert client.get("/api/v1/profile", headers=token_headers()).json() == saved


def test_auth_change_waits_for_inflight_profile_transaction(committed_engine, settings, token_headers, profile_id):
    from fastapi.security import HTTPAuthorizationCredentials

    engine = committed_engine
    with Session(engine, expire_on_commit=False) as session:
        token = token_headers()["Authorization"].split(" ", 1)[1]
        principal = require_authenticated_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), settings, session)
        started, pid = Event(), []
        def deactivate():
            with engine.begin() as connection:
                pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                connection.execute(text("UPDATE auth_user SET is_active=FALSE WHERE id=:id"), {"id": int(profile_id)})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(deactivate)
            try:
                assert started.wait(3)
                wait_for_lock(engine, pid[0])
                UserProfileRepositoryPg(session, principal.user_id).create_or_update(0, {"email": "before@example.com"})
            finally:
                session.rollback()
            future.result(timeout=5)
    with TestClient(create_app(settings)) as client:
        assert client.put("/api/v1/profile", headers=token_headers(), json={"expected_version": 1, "email": None}).status_code == 401
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version FROM user_profiles WHERE user_id=:id"), {"id": profile_id}) == 1


def test_additive_migration_preserves_legacy_data_and_is_idempotent(committed_engine):
    sql = Path("/profile-db/versions.sql").read_text()
    with committed_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TEMP TABLE user_profiles (user_id TEXT, email TEXT, additional_info JSONB) ON COMMIT DROP")
        connection.exec_driver_sql("INSERT INTO user_profiles VALUES ('legacy-user', 'unchanged-synthetic', '{}')")
        connection.execute(text(Path("/profile-db/audit_profiles.sql").read_text()))
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
        assert tuple(connection.exec_driver_sql("SELECT * FROM user_profiles").one()) == ("legacy-user", "unchanged-synthetic", {}, 1)
        with connection.begin_nested():
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql("UPDATE user_profiles SET version=0")
            # Roll back the failed statement before leaving the nested transaction.
            connection.get_nested_transaction().rollback()


@pytest.mark.parametrize("change", ["inactive", "password", "deleted"])
def test_revocation_committed_while_authentication_waits_is_rechecked(committed_engine, settings, token_headers, profile_id, change):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    engine, started, pid = committed_engine, Event(), []
    token = token_headers()["Authorization"].split(" ", 1)[1]
    with engine.connect() as first:
        transaction = first.begin()
        query = {"inactive": "UPDATE auth_user SET is_active=FALSE WHERE id=:id",
                 "password": "UPDATE auth_user SET password='synthetic-changed' WHERE id=:id",
                 "deleted": "DELETE FROM auth_user WHERE id=:id"}[change]
        first.execute(text(query), {"id": int(profile_id)})
        def authenticate():
            with Session(engine) as session:
                pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                with pytest.raises(HTTPException) as caught:
                    require_authenticated_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), settings, session)
                assert caught.value.status_code == 401
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(authenticate)
            try:
                assert started.wait(3)
                wait_for_lock(engine, pid[0])
            finally:
                transaction.commit()
            future.result(timeout=5)


@pytest.mark.parametrize(("definition", "value"), [("INTEGER NOT NULL", "1"), ("BIGINT", "NULL"), ("BIGINT NOT NULL", "0")])
def test_partial_incompatible_migration_fails_without_leaking_or_repairing_rows(committed_engine, definition, value):
    from sqlalchemy.exc import DBAPIError

    with committed_engine.begin() as connection:
        # Definitions/values are fixed test parameters, never request input.
        connection.exec_driver_sql(f"CREATE TEMP TABLE user_profiles (email TEXT, version {definition}) ON COMMIT DROP")
        connection.exec_driver_sql(f"INSERT INTO user_profiles VALUES ('private-synthetic-contact', {value})")
        before = tuple(connection.exec_driver_sql("SELECT * FROM user_profiles").one())
        nested = connection.begin_nested()
        with pytest.raises(DBAPIError) as caught:
            connection.exec_driver_sql(Path("/profile-db/versions.sql").read_text())
        nested.rollback()
        assert "explicit repair" in str(caught.value.orig)
        assert "private-synthetic-contact" not in str(caught.value.orig)
        assert tuple(connection.exec_driver_sql("SELECT * FROM user_profiles").one()) == before
