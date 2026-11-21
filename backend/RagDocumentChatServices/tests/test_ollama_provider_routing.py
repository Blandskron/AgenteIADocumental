from __future__ import annotations

from types import SimpleNamespace

from app.config.settings import Settings
from app.infrastructure.ai.groq_config_resolver import GroqConfigResolver
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.infrastructure.ai.llm_provider_openai_compatible import OpenAICompatibleLLMProvider
from app.interfaces.api.v1.dependencies import build_llm_provider


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _SequencedSession:
    def __init__(self, rows):
        self._rows = list(rows)

    def execute(self, _stmt):
        return _FakeResult(self._rows.pop(0) if self._rows else None)


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://rag_chat_runtime@localhost:5432/documents_db",
        groq_api_key="",
        groq_chat_model="openai/gpt-oss-20b",
    )


def test_resolver_routes_to_local_ollama_when_active_provider_is_ollama() -> None:
    session = _SequencedSession([
        SimpleNamespace(status="ENABLED", config={"active_provider": "ollama"}),
        SimpleNamespace(
            status="ENABLED",
            config={"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:3b", "params": {"max_tokens": 512}},
        ),
    ])
    cfg = GroqConfigResolver().resolve_active_provider(session, _settings(), "tenant-1")
    assert cfg.provider == "ollama"
    assert cfg.model == "qwen2.5:3b"
    assert cfg.base_url == "http://127.0.0.1:11434/v1"
    provider = build_llm_provider(_settings(), effective=cfg)
    assert isinstance(provider, OpenAICompatibleLLMProvider)


def test_resolver_falls_back_to_groq_when_router_is_absent() -> None:
    session = _SequencedSession([None, None])
    cfg = GroqConfigResolver().resolve_active_provider(session, _settings(), "tenant-1")
    assert cfg.provider == "groq"
    provider = build_llm_provider(_settings(), effective=cfg)
    assert isinstance(provider, GroqLLMProvider)
    assert not isinstance(provider, OpenAICompatibleLLMProvider)

