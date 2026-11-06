import re
from uuid import uuid4

import jwt
import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import get_settings
from app.main import app
from database_support import SQL_ROOT, execute_script


@pytest.fixture
def runtime(configured_client, signing_key, engine, runtime_engine):
    client, _ = configured_client
    owner, document, foreign = int(uuid4().hex[:12], 16), uuid4().hex, uuid4().hex
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO documents(document_id,owner_user_id,filename,storage_path,mime_type)
            VALUES (:id,:owner,'synthetic.txt','synthetic.txt','text/plain')
        """), [{"id": document, "owner": str(owner)}, {"id": foreign, "owner": str(owner + 1)}])
    headers = {"Authorization": "Bearer " + jwt.encode({"user_id": owner, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")}
    try:
        yield client, headers, engine, runtime_engine, owner, document, foreign
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)})
            connection.execute(text("DELETE FROM documents WHERE document_id IN (:id,:foreign)"), {"id": document, "foreign": foreign})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0


def test_http_workflow_uses_actual_runtime_login_and_reference_helper(runtime):
    client, headers, admin, configured, owner, document, foreign = runtime
    with configured.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "document_transfer_runtime"
        assert connection.scalar(text("SELECT session_user")) == "document_transfer_runtime"
    assert client.get("/api/v1/health/db").status_code == 200
    row = client.post("/api/v1/transfers", headers=headers, json={"filename": "synthetic.txt", "direction": "UPLOAD", "document_id": document,
                      "status": "RUNNING", "progress": 65, "metadata": {"conversation_id": "synthetic"}})
    assert row.status_code == 200, row.text
    identifier = row.json()["transfer_id"]
    assert row.json()["owner_user_id"] == str(owner)
    assert client.post("/api/v1/transfers", headers=headers, json={"filename": "synthetic.txt", "direction": "UPLOAD", "document_id": foreign}).status_code == 404
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"metadata": {"error": "synthetic"}, "size_bytes": 0}).status_code == 200
    assert client.get("/api/v1/transfers", headers=headers).json()["items"][0]["metadata"] == {"error": "synthetic"}
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 0}
    with admin.begin() as connection:
        connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})
    row = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": "COMPLETED", "progress": 100})
    assert row.status_code == 200 and row.json()["document_id"] is None
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 1}
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 0}
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": foreign}) == 1


@pytest.mark.parametrize("statement", [
    "SELECT storage_path FROM documents LIMIT 0", "SELECT filename FROM documents LIMIT 0", "SELECT processing_error FROM documents LIMIT 0",
    "SELECT * FROM auth_user LIMIT 0", "SELECT * FROM tenants LIMIT 0", "SELECT * FROM document_embeddings LIMIT 0",
    "SELECT allow_download FROM document_assignments LIMIT 0", "UPDATE documents SET filename='forbidden' WHERE false",
    "UPDATE documents SET document_id=document_id WHERE false", "DELETE FROM documents WHERE false",
    "DELETE FROM document_assignments WHERE false", "UPDATE transfer_events SET owner_user_id='43' WHERE false",
    "UPDATE transfer_events SET filename='forbidden' WHERE false", "UPDATE transfer_events SET direction='DOWNLOAD' WHERE false",
    "UPDATE transfer_events SET created_at=now() WHERE false", "INSERT INTO transfer_events(transfer_id) VALUES ('forbidden')",
    "TRUNCATE transfer_events", "CREATE TABLE public.transfer_forbidden(id integer)", "SET ROLE document_transfer_reference_owner",
])
def test_runtime_denies_unrelated_or_immutable_operations(runtime_engine, statement):
    with runtime_engine.connect() as connection:
        with pytest.raises(DBAPIError) as failure:
            connection.execute(text(statement))
        assert failure.value.orig.sqlstate == "42501"
        connection.rollback()
        assert connection.scalar(text("SELECT 1")) == 1


def test_helper_uses_public_table_despite_temporary_shadow(runtime):
    _, _, _, configured, _, document, _ = runtime
    with configured.begin() as connection:
        connection.execute(text("CREATE TEMP TABLE documents(document_id text)"))
        connection.execute(text("INSERT INTO documents VALUES ('synthetic-shadow-only')"))
        assert connection.scalar(text("SELECT public.transfer_lock_document_reference(:id)"), {"id": document}) is True
        assert connection.scalar(text("SELECT public.transfer_lock_document_reference('synthetic-shadow-only')")) is False
        assert connection.scalar(text("SELECT public.transfer_lock_document_reference(NULL::text)")) is None


@pytest.fixture
def isolated_database(engine):
    name = "transfer007_" + uuid4().hex
    admin = create_engine(engine.url, isolation_level="AUTOCOMMIT")
    isolated = None
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True
        isolated = create_engine(engine.url.set(database=name))
        with isolated.connect() as connection:
            execute_script(connection, SQL_ROOT / "run_all.sql")
            connection.commit()
        with isolated.begin() as connection:
            for _ in range(2):
                execute_script(connection, SQL_ROOT / "transfer/permissions.sql")
                execute_script(connection, SQL_ROOT / "transfer/verify_role.sql")
        yield isolated
    finally:
        if isolated is not None:
            isolated.dispose()
        if created:
            assert re.fullmatch(r"transfer007_[0-9a-f]{32}", name)
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.mark.parametrize("change", [
    "GRANT UPDATE(document_id) ON public.documents TO document_transfer_runtime",
    "GRANT SELECT(storage_path) ON public.documents TO document_transfer_runtime",
    "GRANT EXECUTE ON FUNCTION public.transfer_lock_document_reference(text) TO PUBLIC",
    "GRANT EXECUTE ON FUNCTION public.transfer_lock_document_reference(text) TO postgres",
    "GRANT EXECUTE ON FUNCTION public.transfer_lock_document_reference(text) TO document_transfer_runtime WITH GRANT OPTION",
    "GRANT SELECT(document_id) ON public.documents TO document_transfer_runtime WITH GRANT OPTION",
])
def test_verifier_detects_drift_without_changing_shared_database(isolated_database, change):
    with isolated_database.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(change))
        with pytest.raises(psycopg.Error):
            execute_script(connection, SQL_ROOT / "transfer/verify_role.sql")
        transaction.rollback()
        execute_script(connection, SQL_ROOT / "transfer/verify_role.sql")


@pytest.mark.parametrize("change", [
    "REVOKE EXECUTE ON FUNCTION public.transfer_lock_document_reference(text) FROM document_transfer_runtime",
    "REVOKE SELECT(document_id) ON public.documents FROM document_transfer_reference_owner",
])
def test_readiness_detects_runtime_or_helper_owner_acl_failure(isolated_database, configured_client, change):
    client, _ = configured_client
    configured = create_engine(make_url(get_settings().database_url).set(database=isolated_database.url.database))

    def session():
        with Session(configured) as current:
            yield current
    app.dependency_overrides[get_session] = session
    try:
        assert client.get("/api/v1/health/db").status_code == 200
        with isolated_database.begin() as connection:
            connection.execute(text(change))
        response = client.get("/api/v1/health/db")
        assert response.status_code == 503 and response.json() == {"detail": "Document transfer dependencies are unavailable."}
        assert client.get("/api/v1/health").status_code == 200
    finally:
        app.dependency_overrides.pop(get_session, None)
        configured.dispose()
