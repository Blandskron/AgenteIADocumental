from concurrent.futures import ThreadPoolExecutor
from os import environ
from secrets import randbits
from threading import Barrier
from time import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.application.use_cases.manage_conversations import ManageConversations
from app.config.settings import get_settings
from app.infrastructure.database.models import ConversationDocumentModel
from app.infrastructure.database.repositories.conversation_repository_pg import ConversationRepositoryPg
from app.interfaces.api.v1.routes.conversation_routes import add_document
from app.main import app


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def client(signing_key, monkeypatch, tmp_path):
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    settings = get_settings().model_copy(update={
        "auth_jwt_public_key_path": str(public_key),
        "auth_jwt_algorithm": "RS256",
    })
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)
    with TestClient(app) as client:
        yield client


def bearer(signing_key, user_id, **extra_claims):
    claims = {"user_id": user_id, "exp": int(time()) + 60, "token_type": "access", **extra_claims}
    return {"Authorization": f"Bearer {jwt.encode(claims, signing_key, algorithm='RS256')}"}


@pytest.mark.parametrize(("claim", "value"), [
    ("user_id", None), ("user_id", 0), ("user_id", -1), ("user_id", True),
    ("user_id", "12"), ("user_id", 12.5), ("user_id", []),
    ("exp", None), ("exp", 0), ("exp", []), ("exp", "4102444800"), ("exp", 4102444800.5),
    ("token_type", None), ("token_type", "refresh"),
])
def test_rejects_invalid_token_claims(client, signing_key, claim, value):
    claims = {"user_id": 12, "exp": int(time()) + 60, "token_type": "access", "sub": "12", "username": "12"}
    if value is None:
        del claims[claim]
    else:
        claims[claim] = value
    token = jwt.encode(claims, signing_key, algorithm="RS256")
    response = client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_rejects_tokens_from_another_signer(client):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = client.get("/api/v1/conversations", headers=bearer(other_key, 12))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.fixture
def fixture_engine():
    engine = create_engine(environ["CONVERSATION_TEST_DATABASE_URL"])
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def records(fixture_engine):
    engine = create_engine(get_settings().database_url)
    suffix = uuid4().hex
    tenant = f"tenant-{suffix}"
    actor, other = (randbits(60) * 2 + parity for parity in (1, 2))
    document_ids = {kind: f"{kind}-{suffix}" for kind in (
        "owned", "private", "legacy-owner", "legacy-tenant", "group", "assigned",
    )}
    try:
        with fixture_engine.begin() as session:
            session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic')"), {"id": tenant})
            session.execute(text("""
                INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, metadata)
                VALUES (:id, :tenant, :owner, 'fixture.txt', 'fixture.txt', 'text/plain', CAST(:metadata AS jsonb))
            """), [
                {"id": document_ids["owned"], "tenant": tenant, "owner": str(actor), "metadata": "{}"},
                {"id": document_ids["private"], "tenant": tenant, "owner": str(other), "metadata": "{}"},
                {"id": document_ids["legacy-owner"], "tenant": None, "owner": None,
                 "metadata": f'{{"owner_user_id":"{actor}"}}'},
                {"id": document_ids["legacy-tenant"], "tenant": None, "owner": None,
                 "metadata": f'{{"tenant_id":"{tenant}"}}'},
                {"id": document_ids["group"], "tenant": None, "owner": str(other),
                 "metadata": '{"owner_groups":["synthetic-group"]}'},
                {"id": document_ids["assigned"], "tenant": tenant, "owner": str(other), "metadata": "{}"},
            ])
            session.execute(text("""
                INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id)
                VALUES (:document, :tenant, :actor, :other)
            """), {"document": document_ids["assigned"], "tenant": tenant, "actor": str(actor), "other": str(other)})
        with Session(engine) as session:
            conversation_id = ConversationRepositoryPg(session, {"user_id": actor}).create("Synthetic").conversation_id

        yield engine, conversation_id, actor, other, tenant, document_ids
    finally:
        with fixture_engine.begin() as connection:
            connection.execute(text("DELETE FROM conversations WHERE owner_user_id = :actor"), {"actor": str(actor)})
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
def test_revoked_assignment_hides_link_but_owner_can_remove_it(records, fixture_engine, status):
    engine, conversation, actor, _, _, documents = records
    document_id = documents["assigned"]
    with Session(engine) as session:
        repo = ConversationRepositoryPg(session, {"user_id": actor})
        assert repo.add_document(conversation, document_id)
        assert repo.list_documents(conversation) == [document_id]

        with fixture_engine.begin() as connection:
            connection.execute(text("UPDATE document_assignments SET status = :status WHERE document_id = :id"), {
                "status": status, "id": document_id,
            })
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


def test_http_isolation_uses_only_signed_user_id(client, signing_key, records):
    _, conversation, actor, other, _, documents = records
    collection = "/api/v1/conversations"
    detail = f"{collection}/{conversation}"
    messages = f"{detail}/messages"
    links = f"{detail}/documents"
    link = f"{links}/{documents['owned']}"
    owner = bearer(signing_key, actor, username="renamed-owner")
    outsider = bearer(signing_key, other, sub=str(actor), username=str(actor), roles=["SUPERADMIN"])

    assert client.get(detail, headers=owner).json()["owner_user_id"] == str(actor)
    assert client.patch(detail, headers=owner, json={"title": "Synthetic private"}).status_code == 200
    message = {"role": "user", "content": "Synthetic private message"}
    assert client.post(messages, headers=owner, json=message).status_code == 200
    assert client.post(link, headers=owner).json() == {"deleted": True}

    assert all(row["conversation_id"] != conversation for row in client.get(collection, headers=outsider).json())
    assert client.get(detail, headers=outsider).status_code == 404
    assert client.patch(detail, headers=outsider, json={"title": "Denied"}).status_code == 404
    assert client.delete(detail, headers=outsider).json() == {"deleted": False}
    assert client.get(messages, headers=outsider).json() == []
    assert client.post(messages, headers=outsider, json=message).status_code == 404
    assert client.get(links, headers=outsider).json() == {"document_ids": []}
    assert client.post(link, headers=outsider).status_code == 404
    assert client.delete(link, headers=outsider).json() == {"deleted": False}

    assert client.get(detail, headers=owner).json()["title"] == "Synthetic private"
    assert [row["content"] for row in client.get(messages, headers=owner).json()] == [message["content"]]
    assert client.get(links, headers=owner).json() == {"document_ids": [documents["owned"]]}


def test_history_pages_use_stable_order_with_identical_timestamps(client, signing_key, records):
    engine, conversation, actor, other, _, _ = records
    path = f"/api/v1/conversations/{conversation}/messages"
    headers = bearer(signing_key, actor)
    with engine.begin() as connection:
        # Existing data can predate the new write limits.
        connection.execute(text("""
            INSERT INTO conversation_messages (message_id, conversation_id, owner_user_id, role, content, created_at)
            SELECT :conversation || '-' || lpad(i::text, 2, '0'), :conversation, :owner,
                   'user', repeat('a', CASE WHEN i = 1 THEN 33000 ELSE 1 END), '2025-01-01T00:00:00Z'
            FROM generate_series(1, 53) AS i
        """), {"conversation": conversation, "owner": str(actor)})

    latest = client.get(path, headers=headers).json()
    assert [row["message_id"] for row in latest] == [f"{conversation}-{i:02}" for i in range(4, 54)]
    assert client.post(path, headers=headers, json={"role": "user", "content": "New message"}).status_code == 200
    cursor = latest[0]["message_id"]
    older = client.get(path, headers=headers, params={"before": cursor, "limit": 2}).json()
    assert [row["message_id"] for row in older] == [f"{conversation}-02", f"{conversation}-03"]
    oldest = client.get(path, headers=headers, params={"before": older[0]["message_id"]}).json()
    assert [row["message_id"] for row in oldest] == [f"{conversation}-01"]
    assert len(oldest[0]["content"]) == 33_000
    assert client.get(path, headers=headers, params={"before": oldest[0]["message_id"]}).json() == []
    assert client.get(path, headers=headers, params={"before": "missing"}).json() == []
    assert client.get(path, headers=bearer(signing_key, other), params={"before": cursor}).json() == []
    assert client.get(path, headers=headers, params={"limit": 101}).status_code == 422


@pytest.mark.parametrize(("endpoint", "method", "payload"), [
    ("", "POST", {"title": "a" * 257}),
    ("", "POST", {"metadata": {"data": "é" * 8192}}),
    ("/{conversation}", "PATCH", {"title": "a" * 257}),
    ("/{conversation}/messages", "POST", {"role": "user", "content": "a" * 32_769}),
    ("/{conversation}/messages", "POST", {"role": "assistant", "content": "Answer", "sources": [{}] * 51}),
    ("/{conversation}/messages", "POST", {"role": "assistant", "content": "Answer", "sources": [{"content": "a" * 262_144}]}),
    ("/{conversation}/messages", "POST", {"role": "user", "content": "Question", "metadata": {"data": "a" * 16_384}}),
])
def test_write_limits(client, signing_key, records, endpoint, method, payload):
    _, conversation, actor, *_ = records
    path = "/api/v1/conversations" + endpoint.format(conversation=conversation)
    assert client.request(method, path, headers=bearer(signing_key, actor), json=payload).status_code == 422
