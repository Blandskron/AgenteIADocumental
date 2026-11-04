from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.application.use_cases.manage_conversations import ManageConversations
from app.config.settings import get_settings
from app.infrastructure.database.models import ConversationDocumentModel
from app.infrastructure.database.repositories.conversation_repository_pg import ConversationRepositoryPg
from app.interfaces.api.v1.routes.conversation_routes import add_document


@pytest.fixture
def records():
    engine = create_engine(get_settings().database_url)
    suffix = uuid4().hex
    tenant = f"tenant-{suffix}"
    actor = f"actor-{suffix}"
    other = f"other-{suffix}"
    document_ids = {kind: f"{kind}-{suffix}" for kind in (
        "owned", "private", "legacy-owner", "legacy-tenant", "group", "assigned",
    )}
    try:
        with Session(engine) as session:
            session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic')"), {"id": tenant})
            session.execute(text("""
                INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, metadata)
                VALUES (:id, :tenant, :owner, 'fixture.txt', 'fixture.txt', 'text/plain', CAST(:metadata AS jsonb))
            """), [
                {"id": document_ids["owned"], "tenant": tenant, "owner": actor, "metadata": "{}"},
                {"id": document_ids["private"], "tenant": tenant, "owner": other, "metadata": "{}"},
                {"id": document_ids["legacy-owner"], "tenant": None, "owner": None,
                 "metadata": f'{{"owner_user_id":"{actor}"}}'},
                {"id": document_ids["legacy-tenant"], "tenant": None, "owner": None,
                 "metadata": f'{{"tenant_id":"{tenant}"}}'},
                {"id": document_ids["group"], "tenant": None, "owner": other,
                 "metadata": '{"owner_groups":["synthetic-group"]}'},
                {"id": document_ids["assigned"], "tenant": tenant, "owner": other, "metadata": "{}"},
            ])
            session.execute(text("""
                INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id)
                VALUES (:document, :tenant, :actor, :other)
            """), {"document": document_ids["assigned"], "tenant": tenant, "actor": actor, "other": other})
            conversation_id = ConversationRepositoryPg(session, {"user_id": actor}).create("Synthetic").conversation_id

        yield engine, conversation_id, actor, other, tenant, document_ids
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM conversations WHERE owner_user_id = :actor"), {"actor": actor})
            connection.execute(text("DELETE FROM documents WHERE document_id = ANY(:ids)"), {"ids": list(document_ids.values())})
            connection.execute(text("DELETE FROM tenants WHERE tenant_id = :id"), {"id": tenant})
        engine.dispose()


def test_document_access_and_hidden_errors(records):
    engine, conversation, actor, other, tenant, documents = records
    with Session(engine) as session:
        repo = ConversationRepositoryPg(session, {"user_id": actor})
        use_case = ManageConversations(repo)
        for document in (documents["private"], "missing"):
            with pytest.raises(HTTPException) as error:
                add_document(conversation, document, use_case)
            assert (error.value.status_code, error.value.detail) == (404, "Conversation or document not found.")

        assert add_document(conversation, documents["owned"], use_case).deleted
        assert repo.add_document(conversation, documents["legacy-owner"])
        assert not repo.add_document(conversation, documents["group"])
        assert not repo.add_document(conversation, documents["legacy-tenant"])
        assert not repo.add_document("missing", documents["owned"])

        tenant_admin = ConversationRepositoryPg(session, {
            "user_id": actor, "tenant_memberships": [{"tenant_id": tenant, "role": "TENANT_ADMIN"}],
        })
        assert tenant_admin.add_document(conversation, documents["private"])
        assert tenant_admin.add_document(conversation, documents["legacy-tenant"])
        group_member = ConversationRepositoryPg(session, {"user_id": actor, "groups": ["synthetic-group"]})
        assert group_member.add_document(conversation, documents["group"])
        superadmin = ConversationRepositoryPg(session, {"user_id": actor, "roles": ["SUPERADMIN"]})
        assert superadmin.add_document(conversation, documents["group"])
        assert set(superadmin.list_documents(conversation)) == {
            documents[kind] for kind in ("owned", "legacy-owner", "private", "legacy-tenant", "group")
        }
        assert set(repo.list_documents(conversation)) == {documents["owned"], documents["legacy-owner"]}

        outsider = ConversationRepositoryPg(session, {"user_id": other, "roles": ["SUPERADMIN"]})
        assert not outsider.add_document(conversation, documents["owned"])
        assert outsider.list_documents(conversation) == []
        assert not outsider.remove_document(conversation, documents["owned"])


@pytest.mark.parametrize("status", ["CANCELLED", "EXPIRED"])
def test_revoked_assignment_hides_link_but_owner_can_remove_it(records, status):
    engine, conversation, actor, _, _, documents = records
    document_id = documents["assigned"]
    with Session(engine) as session:
        repo = ConversationRepositoryPg(session, {"user_id": actor})
        assert repo.add_document(conversation, document_id)
        assert repo.list_documents(conversation) == [document_id]

        session.execute(text("UPDATE document_assignments SET status = :status WHERE document_id = :id"), {
            "status": status, "id": document_id,
        })
        session.commit()
        assert repo.list_documents(conversation) == []
        assert not repo.add_document(conversation, document_id)
        assert repo.remove_document(conversation, document_id)
        assert not repo.remove_document(conversation, document_id)


def test_concurrent_retries_store_one_link(records):
    engine, conversation, actor, _, _, documents = records
    document_id = documents["owned"]
    barrier = Barrier(2, timeout=5)

    def link():
        with Session(engine) as session:
            barrier.wait()
            return ConversationRepositoryPg(session, {"user_id": actor}).add_document(conversation, document_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(link) for _ in range(2)]
        assert all(attempt.result(timeout=10) for attempt in attempts)

    with Session(engine) as session:
        count = session.scalar(select(func.count()).select_from(ConversationDocumentModel).where(
            ConversationDocumentModel.conversation_id == conversation,
            ConversationDocumentModel.document_id == document_id,
        ))
        assert count == 1
