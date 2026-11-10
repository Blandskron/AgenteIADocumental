import json
from os import environ
from time import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.application.embeddings.use_cases.search_similar_chunks import SearchSimilarChunks
from app.config.security import require_authenticated_user
from app.config.settings import Settings
from app.domain.embeddings import SearchResult
from app.infrastructure.database.repositories.chat_history_repository_pg import ChatHistoryRepositoryPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.interfaces.api.v1.dependencies import get_ask_document_chat
from app.interfaces.api.v1.schemas.chat_schema import ChatAskRequest
from app.shared.errors import ExternalServiceError


VECTOR = [1.0] + [0.0] * 383


@pytest.mark.parametrize("question", ["¿Qué dice?", "Haz un resumen"])
@pytest.mark.parametrize("role", ["USER", "TENANT_ADMIN"])
def test_group_sharing_respects_tenants_and_canonical_identity(session, question, role):
    own_tenant, foreign_tenant = uuid4().hex, uuid4().hex
    actor = uuid4().int % (2**60) + 1
    group = "synthetic-shared-" + uuid4().hex
    for tenant in (own_tenant, foreign_tenant):
        session.execute(text("INSERT INTO tenants(tenant_id,name) VALUES(:id,'Synthetic')"), {"id": tenant})
    documents = {}
    for kind, tenant, metadata in (
        ("local", own_tenant, {"owner_groups": [group]}),
        ("foreign", foreign_tenant, {"owner_groups": [group]}),
        ("global", None, {"owner_groups": [group]}),
        ("conflicting_owner", foreign_tenant, {"owner_user_id": str(actor)}),
        ("conflicting_tenant", foreign_tenant, {"tenant_id": own_tenant}),
        ("legacy", None, {"tenant_id": own_tenant, "owner_groups": [group]}),
    ):
        identifier = documents[kind] = uuid4().hex
        session.execute(text("""INSERT INTO documents(document_id,tenant_id,owner_user_id,filename,storage_path,mime_type,metadata)
            VALUES(:id,:tenant,:owner,'Synthetic.txt','Synthetic.txt','text/plain',CAST(:metadata AS jsonb))"""),
                        {"id": identifier, "tenant": tenant, "owner": str(actor + 1), "metadata": json.dumps(metadata)})
        session.execute(text("""INSERT INTO document_embeddings(document_id,chunk_index,chunk_content,embedding)
            VALUES(:id,0,'Synthetic chunk',CAST(:vector AS vector))"""), {"id": identifier, "vector": str(VECTOR)})
    session.execute(text("SET LOCAL ROLE rag_chat_runtime"))
    user = {"user_id": actor, "groups": [group], "tenant_memberships": [{"tenant_id": own_tenant, "role": role}]}
    repository = VectorRepositoryPgVector(session, user)
    provider = RecordingProvider()
    chat = AskDocumentChat(SearchSimilarChunks(FixedEmbedding(), repository, limit=24), provider)
    answer = chat.execute(question, document_ids=list(documents.values()))
    expected = {documents[kind] for kind in ("local", "global", "legacy")}
    assert provider.document_ids == expected
    assert {source.document_id for source in answer.sources} == expected


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.parametrize("claims", [
    {},
    {"user_id": 42},
    {"user_id": True, "exp": 4102444800},
    {"user_id": "42", "exp": 4102444800},
    {"user_id": 0, "exp": 4102444800},
    {"user_id": 42, "exp": 0},
    {"user_id": 42, "exp": []},
    {"user_id": 42, "exp": "4102444800"},
    {"user_id": 42, "exp": 4102444800, "token_type": "refresh"},
])
def test_invalid_tokens(signing_key, tmp_path, claims):
    with pytest.raises(HTTPException) as error:
        authenticate(signing_key, tmp_path, claims)
    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def authenticate(signing_key, tmp_path, claims):
    public_key = tmp_path / "public.pem"
    public_key.write_bytes(signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    token = jwt.encode(
        {"token_type": "access", "sub": "42", "username": "42", **claims}, signing_key, algorithm="RS256",
    )
    return require_authenticated_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        Settings(database_url="fixture", auth_jwt_public_key_path=str(public_key)),
    )


def test_service_claim_does_not_grant_chat_permission(signing_key, tmp_path):
    user = authenticate(signing_key, tmp_path, {"user_id": 42, "exp": int(time()) + 60, "is_service": True})
    assert user["user_id"] == 42
    with pytest.raises(HTTPException) as error:
        get_ask_document_chat(session=None, settings=Settings(database_url="fixture"), current_user=user)
    assert error.value.status_code == 403


@pytest.fixture
def session():
    engine = create_engine(environ["RAG_CHAT_TEST_DATABASE_URL"])
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                yield session
            transaction.rollback()
    finally:
        engine.dispose()


class FixedEmbedding:
    def embed_text(self, _question):
        return VECTOR


class RecordingProvider:
    def answer_with_context(self, question, context, history, mode):
        self.document_ids = {result.document_id for result in context}
        self.history = [message.content for message in history]
        self.mode = mode
        return "Synthetic answer"


@pytest.mark.parametrize(("question", "mode"), [("¿Qué dice?", "qa"), ("Haz un resumen", "summary")])
def test_revoked_documents_and_previous_answers_are_excluded(session, question, mode):
    tenant, chat_id = uuid4().hex, uuid4().hex
    actor = uuid4().int % (2**60) + 1
    ids = {kind: uuid4().hex for kind in ("owned", "active", "cancelled", "expired", "private")}
    session.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:tenant, 'Synthetic')"), {"tenant": tenant})
    session.execute(text("""
        INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type)
        VALUES (:document, :tenant, :owner, 'fixture.txt', 'fixture.txt', 'text/plain')
    """), [
        {"document": document, "tenant": tenant, "owner": str(actor if kind == "owned" else actor + 1)}
        for kind, document in ids.items()
    ])
    session.execute(text("""
        INSERT INTO document_embeddings (document_id, chunk_index, chunk_content, embedding)
        VALUES (:document, 0, 'Synthetic chunk', CAST(:embedding AS vector))
    """), [{"document": document, "embedding": str(VECTOR)} for document in ids.values()])
    session.execute(text("""
        INSERT INTO document_assignments (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id, status)
        VALUES (:document, :tenant, :recipient, :sender, :status)
    """), [
        {"document": ids[kind], "tenant": tenant, "recipient": str(actor), "sender": str(actor + 1), "status": status}
        for kind, status in (("active", "PENDING"), ("cancelled", "CANCELLED"), ("expired", "EXPIRED"))
    ])
    session.execute(text("SET LOCAL ROLE rag_chat_runtime"))

    current_user = {"user_id": actor, "username": str(actor + 1)}
    history = ChatHistoryRepositoryPg(session, current_user)
    history.save_turn(chat_id, "Synthetic earlier question", "Synthetic legacy answer with revoked material", [])
    ChatHistoryRepositoryPg(session, {"user_id": actor + 1}).save_turn(chat_id, "Synthetic foreign question", "Answer", [])
    history.save_turn("another-session", "Synthetic foreign session question", "Answer", [])
    repository = VectorRepositoryPgVector(session, current_user)
    provider = RecordingProvider()
    chat = AskDocumentChat(SearchSimilarChunks(FixedEmbedding(), repository, limit=5), provider, history)
    answer = chat.execute(question, session_id=chat_id, document_ids=list(ids.values()))

    assert provider.mode == mode
    assert provider.history == ["Synthetic earlier question"]
    assert provider.document_ids == {ids["owned"], ids["active"]}
    assert {source.document_id for source in answer.sources} == provider.document_ids


@pytest.mark.parametrize("payload", [
    {"question": "  "},
    {"question": "x" * 4097},
    {"question": "bad\0input"},
    {"question": "Question", "session_id": "s" * 129},
    {"question": "Question", "document_ids": ["d" * 129]},
    {"question": "Question", "document_ids": [" "]},
    {"question": "Question", "document_ids": [str(i) for i in range(13)]},
])
def test_request_limits(payload):
    with pytest.raises(ValidationError):
        ChatAskRequest.model_validate(payload)


def test_accepts_limits_and_multiline_question():
    payload = ChatAskRequest(question="x" * 4094 + "\ny", session_id="s" * 128, document_ids=[str(i) for i in range(12)])
    assert len(payload.question) == 4096
    assert len(payload.document_ids) == 12


class SyntheticSearch:
    def execute(self, question, document_ids):
        return [SearchResult("doc", str(index), index, "x" * 2400, 1.0) for index in range(30)]


class FailingSearch:
    def execute(self, question, document_ids):
        raise ExternalServiceError("Synthetic retrieval failure")


class FailingProvider:
    def answer_with_context(self, question, context, history, mode):
        raise ExternalServiceError("Synthetic provider failure")


@pytest.mark.parametrize("failure", ["retrieval", "generation", None])
def test_context_limits_and_atomic_turn(session, failure):
    session.execute(text("SET LOCAL ROLE rag_chat_runtime"))
    chat_id = uuid4().hex
    history = ChatHistoryRepositoryPg(session, {"user_id": 42})
    for _ in range(10):
        history.save_turn(chat_id, "q" * 2000, "Earlier answer", [])
    provider = RecordingProvider() if failure != "generation" else FailingProvider()
    search = FailingSearch() if failure == "retrieval" else SyntheticSearch()
    result = AskDocumentChat(search, provider, history).execute("New question", session_id=chat_id)
    rows = session.execute(text("""
        SELECT role, content FROM chat_messages WHERE session_id = :session_id AND owner_user_id = '42'
    """), {"session_id": chat_id}).all()

    if failure:
        assert result.sources == []
        assert len(rows) == 20
    else:
        assert len(provider.history) == 8
        assert all(len(question) == 1000 for question in provider.history)
        assert len(result.sources) == 24
        assert all(len(source.content) == 1200 for source in result.sources)
        assert len(rows) == 22
        assert ("user", "New question") in rows
        assert ("assistant", "Synthetic answer") in rows


def test_database_failure_cannot_persist_half_a_turn(session):
    session.execute(text("SET LOCAL ROLE rag_chat_runtime"))
    chat_id = uuid4().hex
    history = ChatHistoryRepositoryPg(session, {"user_id": 42})
    with pytest.raises(DBAPIError):
        history.save_turn(chat_id, "Synthetic question", None, [])
    session.rollback()
    assert session.scalar(text("SELECT count(*) FROM chat_messages WHERE session_id = :id"), {"id": chat_id}) == 0
