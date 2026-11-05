import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.config.database import get_session
from app.infrastructure.database.models import DocumentModel
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.main import app


@pytest.mark.parametrize("statement", [
    "SELECT password FROM auth_user LIMIT 0",
    "SELECT * FROM tenants LIMIT 0",
    "SELECT * FROM tenant_memberships LIMIT 0",
    "SELECT embedding FROM document_embeddings LIMIT 0",
    "SELECT content FROM conversation_messages LIMIT 0",
    "UPDATE auth_user SET is_superuser = true WHERE false",
    "UPDATE documents SET metadata = '{}' WHERE false",
    "UPDATE document_assignments SET tenant_id = 'forbidden' WHERE false",
    "DELETE FROM audit_logs WHERE false",
    "DELETE FROM document_assignment_events WHERE false",
    "TRUNCATE documents",
    "CREATE TABLE public.access_forbidden (id integer)",
    "SET ROLE document_access_authorizer",
])
def test_runtime_rejects_unrelated_reads_and_writes(statement):
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == "document_access_runtime"
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(statement))
            assert error.value.orig.sqlstate == "42501"
    finally:
        engine.dispose()


@pytest.mark.parametrize("entity", ["user", "tenant", "membership"])
def test_authority_functions_hold_locks_until_transaction_finishes(workflow, entity):
    with Session(workflow.runtime_engine) as session:
        repository = DocumentAccessRepositoryPg(session, {"user_id": int(workflow.users["manager"])})
        if entity == "user":
            assert repository._active_user(workflow.users["manager"]) is not None
            statement, identifier = "UPDATE auth_user SET is_active = false WHERE id = :id", int(workflow.users["manager"])
        elif entity == "tenant":
            assert repository._assignment_role(session.get(DocumentModel, workflow.documents["owned"])) == "TENANT_ADMIN"
            statement, identifier = "UPDATE tenants SET status = 'DISABLED' WHERE tenant_id = :id", workflow.tenant
        else:
            assert repository._active_membership(workflow.tenant, workflow.users["manager"]) is not None
            statement, identifier = "UPDATE tenant_memberships SET status = 'DISABLED' WHERE user_id = :id", workflow.users["manager"]
        with workflow.engine.connect() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(statement), {"id": identifier})
            assert error.value.orig.sqlstate == "55P03"


def test_authority_lookup_ignores_temporary_table_shadowing(workflow):
    with Session(workflow.runtime_engine) as session:
        session.execute(text("CREATE TEMP TABLE auth_user (id bigint, is_active boolean, is_superuser boolean)"))
        session.execute(text("INSERT INTO pg_temp.auth_user VALUES (:id, true, true)"), {"id": int(workflow.users["recipient"])})
        actor = DocumentAccessRepositoryPg(session)._active_user(workflow.users["recipient"])
        assert actor.is_active and not actor.is_superuser


def test_readiness_checks_runtime_database_and_authority_functions(workflow):
    assert workflow.client.get("/api/v1/health/db").json() == {"status": "ok"}


def test_readiness_failure_returns_503_without_database_details(workflow, monkeypatch):
    class UnavailableSession:
        def scalar(self, statement):
            from sqlalchemy.exc import SQLAlchemyError
            raise SQLAlchemyError("Synthetic connection detail that must remain private")

    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: UnavailableSession())
    response = workflow.client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Document access database is unavailable."}
