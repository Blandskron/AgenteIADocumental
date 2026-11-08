from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.use_cases.manage_exports import ManageExports
from app.config.security import ExportUser, require_authenticated_user
from app.infrastructure.database.repositories.export_repository_pg import ExportRepositoryPg
from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer
from app.interfaces.api.v1.schemas.export_schema import ChatPdfExportRequest
from app.main import create_app
from app.shared.errors import NotFoundError

pytestmark = pytest.mark.postgres

CHANGES = {"inactive": "UPDATE auth_user SET is_active=FALSE WHERE id=:id",
           "password": "UPDATE auth_user SET password='synthetic-changed' WHERE id=:id",
           "deleted": "DELETE FROM auth_user WHERE id=:id"}


def wait_for_lock(engine, pid):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}) == "Lock":
                return
        sleep(0.01)
    raise AssertionError("Expected a real PostgreSQL lock wait")


def credentials(token_headers):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_headers()["Authorization"].split()[1])


@pytest.mark.parametrize("change", CHANGES)
def test_export_first_holds_identity_until_commit(committed_engine, settings, token_headers, owner, change):
    engine = committed_engine
    started, pid = Event(), []
    with Session(engine, expire_on_commit=False) as session:
        principal = require_authenticated_user(credentials(token_headers), settings, session)
        def revoke():
            with engine.begin() as connection:
                connection.execute(text("SET LOCAL statement_timeout='5s'"))
                pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                connection.execute(text(CHANGES[change]), {"id": int(owner)})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(revoke)
            try:
                assert started.wait(3)
                wait_for_lock(engine, pid[0])
                use_case = ManageExports(ExportRepositoryPg(session, principal), ChatPdfRenderer())
                saved = use_case.create_chat_pdf_export(ChatPdfExportRequest(answer="synthetic before revocation"))
                assert saved.owner_user_id == owner
            finally:
                session.rollback()
            future.result(timeout=6)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/exports", headers=token_headers()).status_code == 401


@pytest.mark.parametrize("change", CHANGES)
def test_auth_change_first_is_rechecked_after_lock_wait(committed_engine, settings, token_headers, owner, change):
    engine = committed_engine
    started, pid = Event(), []
    with engine.connect() as first:
        transaction = first.begin()
        first.execute(text(CHANGES[change]), {"id": int(owner)})
        def authenticate():
            with Session(engine) as session:
                session.execute(text("SET LOCAL statement_timeout='5s'"))
                pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                with pytest.raises(HTTPException) as caught:
                    require_authenticated_user(credentials(token_headers), settings, session)
                assert caught.value.status_code == 401
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(authenticate)
            try:
                assert started.wait(3)
                wait_for_lock(engine, pid[0])
            finally:
                transaction.commit()
            future.result(timeout=6)
    assert not settings.export_storage_base_path.exists()


@pytest.mark.parametrize("reference", ["conversation", "message"])
@pytest.mark.parametrize("export_first", [True, False])
def test_reference_changes_serialize_with_export(committed_engine, owner, reference, export_first):
    engine = committed_engine
    conversation, message = uuid4().hex, uuid4().hex
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO conversations (conversation_id,owner_user_id) VALUES (:id,:owner)"), {"id": conversation, "owner": owner})
        connection.execute(text("""INSERT INTO conversation_messages (message_id,conversation_id,owner_user_id,role,content)
                                   VALUES (:id,:conversation,:owner,'assistant','synthetic')"""), {"id": message, "conversation": conversation, "owner": owner})
    query = ("UPDATE conversations SET title='synthetic changed' WHERE conversation_id=:id" if reference == "conversation"
             else "DELETE FROM conversation_messages WHERE message_id=:id")
    identifier = conversation if reference == "conversation" else message
    started, pid = Event(), []
    with Session(engine) as first:
        if export_first:
            ExportRepositoryPg(first, ExportUser(owner)).validate_references(conversation, message)
        else:
            # Delete before validation: the waiting validator must see disappearance.
            query = ("DELETE FROM conversations WHERE conversation_id=:id" if reference == "conversation" else query)
            first.execute(text(query), {"id": identifier})
        def compete():
            with Session(engine) as second:
                second.execute(text("SET LOCAL statement_timeout='5s'"))
                pid.append(second.scalar(text("SELECT pg_backend_pid()")))
                started.set()
                if export_first:
                    second.execute(text(query), {"id": identifier})
                    second.commit()
                else:
                    with pytest.raises(NotFoundError):
                        ExportRepositoryPg(second, ExportUser(owner)).validate_references(conversation, message)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(compete)
            try:
                assert started.wait(3)
                wait_for_lock(engine, pid[0])
            finally:
                first.commit()
            future.result(timeout=6)
