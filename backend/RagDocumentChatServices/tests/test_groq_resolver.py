import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
from cryptography.fernet import Fernet
from openai import OpenAI

from app.application.chat.use_cases.ask_document_chat import ASSISTANT_ERROR_ANSWER, AskDocumentChat
from app.config.settings import Settings
from app.domain.embeddings import SearchResult
from app.infrastructure.ai import llm_provider_groq
from app.infrastructure.ai.groq_config_resolver import GroqConfigResolver
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider


MASTER_KEY = "synthetic-master-key-r104-0123456789abcdef!"
CONTEXT = [SearchResult("synthetic-doc", "chunk-1", 0, "Texto de prueba.", 0.95, "fixture.txt")]


def _encrypt(secret: str, master_key: str = MASTER_KEY, key_id: str = "v1") -> str:
    fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(master_key.encode("utf-8")).digest()))
    return f"secrets1.{key_id}.{fernet.encrypt(secret.encode('utf-8')).decode('ascii')}"


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, row=None):
        self.row = row
        self.queries = 0

    def execute(self, _stmt):
        self.queries += 1
        return _FakeResult(self.row)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://rag_chat_runtime@localhost:5432/documents_db",
        "groq_api_key": "",
        "groq_chat_model": "env-default-model",
        "chat_completion_max_tokens": 2000,
        "chat_completion_temperature": 0.3,
        "chat_completion_timeout_seconds": 60,
        "secrets_encryption_key": MASTER_KEY,
        "secrets_key_id": "v1",
        "secrets_previous_keys": "",
    }
    base.update(overrides)
    return Settings(**base)


def test_resolver_precedence_db_over_env_over_not_configured_and_hot_reload():
    resolver = GroqConfigResolver(ttl_seconds=60)
    t1 = datetime(2026, 11, 21, 18, 0, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=5)

    # 1. Active DB row wins over env fallback
    session = _FakeSession(
        SimpleNamespace(
            status="ENABLED",
            config={"model": "db-model-v1", "max_tokens": 1024, "temperature": 0.2, "timeout_seconds": 30},
            secrets_encrypted=_encrypt("synthetic-db-key-1"),
            updated_at=t1,
        )
    )
    settings = _settings(groq_api_key="synthetic-env-key")
    eff1 = resolver.resolve(session, settings, "tenant-1")
    assert eff1.source == "database"
    assert eff1.api_key == "synthetic-db-key-1"
    assert eff1.model == "db-model-v1"
    assert eff1.max_tokens == 1024

    # 2. Hot update (updated_at changes) invalidates cache immediately without restart
    session.row = SimpleNamespace(
        status="ENABLED",
        config={"model": "db-model-v2"},
        secrets_encrypted=_encrypt("synthetic-db-key-2"),
        updated_at=t2,
    )
    eff2 = resolver.resolve(session, settings, "tenant-1")
    assert eff2.source == "database"
    assert eff2.api_key == "synthetic-db-key-2"
    assert eff2.model == "db-model-v2"

    # 3. Revoked DB row (DISABLED) falls back to .env
    session.row = SimpleNamespace(
        status="DISABLED",
        config={},
        secrets_encrypted=None,
        updated_at=t2 + timedelta(seconds=5),
    )
    eff3 = resolver.resolve(session, settings, "tenant-1")
    assert eff3.source == "env"
    assert eff3.api_key == "synthetic-env-key"
    assert eff3.model == "env-default-model"

    # 4. Neither DB nor .env -> not_configured
    eff4 = resolver.resolve(session, _settings(groq_api_key=""), "tenant-1")
    assert eff4.source == "not_configured"
    assert eff4.api_key == ""


def test_typed_provider_statuses_and_local_embedding_independence(monkeypatch):
    # Track that retrieval (LocalEmbeddingProvider path) executes completely independently of Groq status.
    retrieval_calls = []

    class TrackingSearch:
        def execute(self, question, document_ids):
            retrieval_calls.append((question, document_ids))
            return CONTEXT

    # Case A: not_configured (no key) -> retrieval still runs, provider_status == "not_configured"
    not_cfg = AskDocumentChat(TrackingSearch(), GroqLLMProvider("", "m", 80, 0.3, 4)).execute("Pregunta")
    assert not_cfg.answer == ASSISTANT_ERROR_ANSWER
    assert not_cfg.sources == []
    assert not_cfg.provider_status == "not_configured"
    assert len(retrieval_calls) == 1

    # Case B: 401 -> auth_error, 429 -> rate_limited, 503 -> provider_error
    for status_code, expected_status in ((401, "auth_error"), (429, "rate_limited"), (503, "provider_error")):
        transport = httpx.MockTransport(
            lambda _req, code=status_code: httpx.Response(code, json={"error": {"message": "synthetic"}})
        )
        monkeypatch.setattr(
            llm_provider_groq,
            "OpenAI",
            lambda **kwargs: OpenAI(**kwargs, http_client=httpx.Client(transport=transport, timeout=kwargs["timeout"])),
        )
        provider = GroqLLMProvider("synthetic-key", "fixture-model", 80, 0.3, 4)
        answer = AskDocumentChat(TrackingSearch(), provider).execute("Pregunta")
        assert answer.provider_status == expected_status
        assert answer.sources == []

    # Case C: 200 OK -> provider_status == "ok"
    ok_transport = httpx.MockTransport(
        lambda _req: httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}],
            },
        )
    )
    monkeypatch.setattr(
        llm_provider_groq,
        "OpenAI",
        lambda **kwargs: OpenAI(**kwargs, http_client=httpx.Client(transport=ok_transport, timeout=kwargs["timeout"])),
    )
    ok_answer = AskDocumentChat(TrackingSearch(), GroqLLMProvider("synthetic-key", "fixture-model", 80, 0.3, 4)).execute("Pregunta")
    assert ok_answer.provider_status == "ok"
    assert ok_answer.answer == "OK"
    assert len(ok_answer.sources) == 1
    assert len(retrieval_calls) == 5

