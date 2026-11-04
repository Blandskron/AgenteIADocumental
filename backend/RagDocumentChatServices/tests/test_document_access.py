from time import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.application.embeddings.use_cases.search_similar_chunks import SearchSimilarChunks
from app.config.security import require_authenticated_user
from app.config.settings import Settings, get_settings
from app.infrastructure.database.repositories.chat_history_repository_pg import ChatHistoryRepositoryPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.interfaces.api.v1.dependencies import get_ask_document_chat


VECTOR = [1.0] + [0.0] * 383


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
        get_ask_document_chat(session=None, settings=get_settings(), current_user=user)
    assert error.value.status_code == 403


@pytest.fixture
def session():
    engine = create_engine(get_settings().database_url)
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

    current_user = {"user_id": actor, "username": str(actor + 1)}
    history = ChatHistoryRepositoryPg(session, current_user)
    history.save_user_message(chat_id, "Synthetic earlier question")
    history.save_assistant_message(chat_id, "Synthetic legacy answer with revoked material", [])
    ChatHistoryRepositoryPg(session, {"user_id": actor + 1}).save_user_message(chat_id, "Synthetic foreign question")
    repository = VectorRepositoryPgVector(session, current_user)
    provider = RecordingProvider()
    chat = AskDocumentChat(SearchSimilarChunks(FixedEmbedding(), repository, limit=5), provider, history)
    answer = chat.execute(question, session_id=chat_id, document_ids=list(ids.values()))

    assert provider.mode == mode
    assert provider.history == ["Synthetic earlier question"]
    assert provider.document_ids == {ids["owned"], ids["active"]}
    assert {source.document_id for source in answer.sources} == provider.document_ids
