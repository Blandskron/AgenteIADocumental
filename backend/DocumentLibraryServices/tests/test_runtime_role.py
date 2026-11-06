from os import environ
from uuid import uuid4

import jwt
import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.config.database import get_session
from app.main import app
from database_support import SQL_ROOT, execute_script


@pytest.fixture
def runtime(configured_client, signing_key):
    client, _ = configured_client
    admin = create_engine(environ["LIBRARY_TEST_DATABASE_URL"])
    engine = create_engine(get_settings().database_url)
    owner = str(int(uuid4().hex[:12], 16))
    identifier, foreign = uuid4().hex, uuid4().hex
    folders = []
    try:
        with admin.begin() as connection:
            for doc, user in ((identifier, owner), (foreign, "43")):
                connection.execute(text("""INSERT INTO documents(document_id,owner_user_id,filename,storage_path,mime_type,status)
                    VALUES (:id,:owner,'Synthetic runtime.txt','lib008-synthetic.txt','text/plain','PROCESSED')"""), {"id": doc, "owner": user})
        token = jwt.encode({"user_id": int(owner), "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, engine, admin, owner, identifier, foreign, folders
    finally:
        with admin.begin() as connection:
            connection.execute(text("DELETE FROM documents WHERE document_id IN (:id,:foreign)"), {"id": identifier, "foreign": foreign})
            for folder_id in reversed(folders):
                connection.execute(text("DELETE FROM document_folders WHERE folder_id=:id"), {"id": folder_id})
        engine.dispose()
        admin.dispose()


def test_real_login_can_complete_the_http_library_workflow(runtime):
    client, engine, _, owner, identifier, foreign, folders = runtime
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT session_user")) == "document_library_runtime"
        assert connection.scalar(text("SELECT current_user")) == "document_library_runtime"
    assert client.get("/api/v1/health/db").status_code == 200
    root = client.post("/api/v1/folders", json={"name": "Synthetic root"})
    assert root.status_code == 201, root.text
    root_id = root.json()["folder_id"]
    folders.append(root_id)
    child = client.post("/api/v1/folders", json={"name": "Synthetic child", "parent_folder_id": root_id})
    assert child.status_code == 201, child.text
    child_id = child.json()["folder_id"]
    folders.append(child_id)
    assert root.json()["owner_user_id"] == owner
    assert client.patch(f"/api/v1/folders/{root_id}", json={"name": "Renamed", "metadata": {"synthetic": True}}).status_code == 200
    assert client.get("/api/v1/folders").json()["items"][0]["folder_id"] == root_id
    assert client.get("/api/v1/folders", params={"parent_folder_id": root_id}).json()["items"][0]["folder_id"] == child_id
    for _ in range(2):
        assert client.post(f"/api/v1/folders/{root_id}/documents/{identifier}").json() == {"deleted": True}
        assert client.post(f"/api/v1/library/favorites/{identifier}").json() == {"count": 1}
    listed = client.get(f"/api/v1/folders/{root_id}/documents").json()["items"]
    assert len(listed) == 1 and listed[0]["is_favorite"]
    assert client.get("/api/v1/library/favorites").json()["items"][0]["document_id"] == identifier
    assert client.get("/api/v1/library/recent").json()["items"][0]["document_id"] == identifier
    assert client.post("/api/v1/library/markers", json={"document_ids": [identifier, foreign]}).json() == [{"document_id": identifier, "is_favorite": True}]
    assert client.post(f"/api/v1/library/favorites/{foreign}").json() == {"count": 0}
    assert client.patch(f"/api/v1/library/documents/{identifier}/folder", json={"folder_id": child_id}).json() == {"success": True}
    assert client.delete(f"/api/v1/folders/{child_id}/documents/{identifier}").json() == {"deleted": True}
    assert client.patch(f"/api/v1/library/documents/{identifier}/folder", json={"folder_id": None}).status_code == 200
    assert client.delete(f"/api/v1/library/favorites/{identifier}").json() == {"count": 1}
    assert client.delete(f"/api/v1/folders/{root_id}").json() == {"deleted": True}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == 1


@pytest.mark.parametrize("statement", [
    "SELECT storage_path FROM documents LIMIT 0",
    "SELECT processing_error FROM documents LIMIT 0",
    "SELECT embedding FROM document_embeddings LIMIT 0",
    "SELECT chunk_content FROM document_embeddings LIMIT 0",
    "SELECT * FROM auth_user LIMIT 0",
    "SELECT * FROM tenants LIMIT 0",
    "UPDATE documents SET filename='forbidden' WHERE false",
    "UPDATE documents SET document_id=document_id WHERE false",
    "DELETE FROM documents WHERE false",
    "UPDATE document_folders SET owner_user_id='43' WHERE false",
    "TRUNCATE document_favorites",
    "CREATE TABLE public.library_forbidden(id integer)",
    "SET ROLE document_library_reference_owner",
])
def test_real_login_rejects_unrelated_reads_and_writes(runtime, statement):
    engine = runtime[1]
    with engine.begin() as connection:
        with pytest.raises(DBAPIError) as failure:
            connection.execute(text(statement))
        assert failure.value.orig.sqlstate == "42501"


def test_reference_helper_uses_qualified_table_and_cannot_change_documents(runtime):
    _, engine, _, _, identifier, _, _ = runtime
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TEMP TABLE documents(document_id text)")
        connection.exec_driver_sql("INSERT INTO documents VALUES ('synthetic-shadow-only')")
        assert connection.scalar(text("SELECT public.library_lock_document_reference(:id)"), {"id": identifier}) is True
        assert connection.scalar(text("SELECT public.library_lock_document_reference('synthetic-shadow-only')")) is False
        assert connection.scalar(text("SELECT public.library_lock_document_reference(NULL)")) is None
        assert connection.scalar(text("SELECT filename FROM public.documents WHERE document_id=:id"), {"id": identifier}) == "Synthetic runtime.txt"


def test_privilege_verifier_rejects_drift_without_persisting_it(runtime):
    admin = runtime[2]
    with admin.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql("GRANT UPDATE (document_id) ON public.documents TO document_library_runtime")
        with pytest.raises(psycopg.Error):
            execute_script(connection, SQL_ROOT / "library/verify_role.sql")
        transaction.rollback()
        execute_script(connection, SQL_ROOT / "library/verify_role.sql")


def test_readiness_requires_reference_function_permission(migrated_database, configured_client, monkeypatch):
    engine = create_engine(make_url(get_settings().database_url).set(database=migrated_database.url.database))

    def connection():
        with Session(engine) as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_session, connection)
    client, _ = configured_client
    try:
        assert client.get("/api/v1/health/db").status_code == 200
        with migrated_database.begin() as admin:
            admin.exec_driver_sql("REVOKE EXECUTE ON FUNCTION public.library_lock_document_reference(text) FROM document_library_runtime")
        response = client.get("/api/v1/health/db")
        assert response.status_code == 503 and response.json() == {"detail": "Document library dependencies are unavailable."}
        assert client.get("/api/v1/health").status_code == 200
    finally:
        engine.dispose()
