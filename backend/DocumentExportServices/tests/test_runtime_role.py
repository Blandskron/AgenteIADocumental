import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.main import create_app

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("query", [
    "SELECT password FROM auth_user", "SELECT storage_path FROM document_exports", "SELECT error_message FROM document_exports",
    "SELECT content FROM conversation_messages", "SELECT * FROM documents", "UPDATE auth_user SET is_active=FALSE WHERE FALSE",
    "UPDATE document_exports SET status='FAILED' WHERE FALSE", "DELETE FROM conversations WHERE FALSE",
    "TRUNCATE document_exports", "CREATE TABLE public.export_forbidden(id int)",
    "SELECT public.profile_identity_is_current(1,'A')",
])
def test_role_cannot_read_or_change_unrelated_resources(db_session, query):
    transaction = db_session.begin_nested()
    db_session.execute(text("SET LOCAL ROLE export_runtime"))
    with pytest.raises(DBAPIError) as caught:
        db_session.execute(text(query))
    assert caught.value.orig.sqlstate == "42501"
    transaction.rollback()


def test_exact_acl_and_helpers_are_verified(db_session):
    db_session.connection().exec_driver_sql(Path("/export-db/verify_role.sql").read_text())


def test_real_runtime_login_crud_and_no_update_permission(committed_engine, settings, owner, token_headers):
    url = make_url(settings.database_url).set(username="export_runtime", password=os.environ["EXPORT_TEST_RUNTIME_PASSWORD"])
    configured = settings.model_copy(update={"database_url": url.render_as_string(hide_password=False)})
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == "export_runtime"
            assert connection.scalar(text("SELECT has_table_privilege(current_user,'document_exports','UPDATE')")) is False
            with pytest.raises(DBAPIError) as caught:
                connection.execute(text("SET ROLE export_helper_owner"))
            assert caught.value.orig.sqlstate == "42501"
        with TestClient(create_app(configured)) as client:
            created = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "Runtime synthetic"})
            assert created.status_code == 200
            row = created.json()
            assert client.get("/api/v1/exports", headers=token_headers()).json()["items"][0]["export_id"] == row["export_id"]
            assert client.get(row["download_url"], headers=token_headers()).content.startswith(b"%PDF-")
            assert client.delete("/api/v1/exports/" + row["export_id"], headers=token_headers()).status_code == 200
            assert client.get(row["download_url"], headers=token_headers()).status_code == 404
    finally:
        engine.dispose()
