from __future__ import annotations

import base64
import hashlib
import json

import pytest
from app.infrastructure.llm.model_factory import (
    LLMConfigurationError,
    TenantLLMConfigResolver,
    build_agent_model_client,
    parse_structured_json_fallback,
    validate_provider_base_url,
)

STRONG_TEST_SECRET = "A9x!Synthetic_Key_For_UnitTests_Only_2026_987654"


def _encrypt_envelope(secret_plaintext: str, key_id: str = "v1") -> str:
    fernet_mod = pytest.importorskip("cryptography.fernet")
    fernet = fernet_mod.Fernet(base64.urlsafe_b64encode(hashlib.sha256(STRONG_TEST_SECRET.encode("utf-8")).digest()))
    token = fernet.encrypt(secret_plaintext.encode("utf-8")).decode("ascii")
    return f"secrets1.{key_id}.{token}"


def test_resolver_switches_between_groq_and_ollama_without_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    state = {"active": "groq"}
    encrypted = _encrypt_envelope("gsk_synthetic_groq_key_123456")

    def fake_loader(tenant_id: str, provider: str):
        if provider == "ai_router":
            return {"status": "ENABLED", "config": {"active_provider": state["active"]}}
        if provider == "groq":
            return {
                "status": "ENABLED",
                "config": {"model": "llama-3.3-70b-versatile", "max_tokens": 1500},
                "secrets_encrypted": encrypted,
            }
        if provider == "ollama":
            return {
                "status": "ENABLED",
                "config": {"base_url": "http://ollama:11434", "model": "qwen2.5:3b"},
            }
        return None

    resolver = TenantLLMConfigResolver(row_loader=fake_loader, encryption_key=STRONG_TEST_SECRET, key_id="v1")

    groq_cfg = resolver.resolve("tenant-a")
    assert groq_cfg.provider == "groq"
    assert groq_cfg.api_key == "gsk_synthetic_groq_key_123456"
    assert groq_cfg.source == "database"

    # Switch to Ollama in /settings/ai -> takes effect immediately on next resolution
    state["active"] = "ollama"
    ollama_cfg = resolver.resolve("tenant-a")
    assert ollama_cfg.provider == "ollama"
    assert ollama_cfg.model == "qwen2.5:3b"
    assert ollama_cfg.base_url == "http://ollama:11434/v1"
    assert ollama_cfg.allow_local is True


def test_resolver_degrades_honestly_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    resolver = TenantLLMConfigResolver(row_loader=lambda _t, _p: None)
    cfg = resolver.resolve("tenant-empty")
    assert cfg.source == "not_configured"
    with pytest.raises(LLMConfigurationError) as exc_info:
        build_agent_model_client(cfg)
    assert exc_info.value.code == "not_configured"


def test_ssrf_validation_blocks_metadata_and_private_ips_for_external_providers() -> None:
    assert validate_provider_base_url("https://api.groq.com/openai/v1") == "https://api.groq.com/openai/v1"
    assert validate_provider_base_url("http://ollama:11434/v1", allow_local=True) == "http://ollama:11434/v1"

    for bad_url in (
        "http://169.254.169.254/latest/meta-data",
        "http://127.0.0.1:8001/api",
        "https://10.0.0.5/v1",
        "https://metadata.google.internal/v1",
        "file:///etc/passwd",
    ):
        with pytest.raises(LLMConfigurationError) as exc_info:
            validate_provider_base_url(bad_url, allow_local=False)
        assert exc_info.value.code == "ssrf_blocked"


def test_agent_model_client_supports_native_tool_calls_and_ollama_json_fallback() -> None:
    resolver = TenantLLMConfigResolver(
        row_loader=lambda _t, p: {"status": "ENABLED", "config": {"active_provider": "ollama"}}
        if p == "ai_router"
        else {"status": "ENABLED", "config": {"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:3b"}}
        if p == "ollama"
        else None
    )
    cfg = resolver.resolve("tenant-1")

    # 1. Native tool call
    def native_transport(_url, _payload, _headers, _timeout):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "search_documents",
                                    "arguments": json.dumps({"query": "cláusula penalización", "limit": 5}),
                                }
                            }
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        }

    client = build_agent_model_client(cfg, transport=native_transport)
    resp = client.invoke([{"role": "user", "content": "busca cláusulas"}])
    assert resp.action == "tool_call"
    assert resp.tool_name == "search_documents"
    assert resp.tool_arguments["query"] == "cláusula penalización"
    assert resp.used_json_fallback is False

    # 2. Structured JSON fallback for small local Ollama models
    def fallback_transport(_url, _payload, _headers, _timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"action":"tool_call","name":"get_document_chunks","arguments":{"document_id":"doc-1"}}\n```'
                    }
                }
            ],
            "usage": {"prompt_tokens": 90, "completion_tokens": 25},
        }

    fallback_client = build_agent_model_client(cfg, transport=fallback_transport)
    fb_resp = fallback_client.invoke([{"role": "user", "content": "lee doc-1"}])
    assert fb_resp.action == "tool_call"
    assert fb_resp.tool_name == "get_document_chunks"
    assert fb_resp.used_json_fallback is True

    parsed_final = parse_structured_json_fallback('{"action":"final","answer":"Resumen citado [Fuente 1]"}')
    assert parsed_final is not None
    assert parsed_final.action == "final"
    assert "[Fuente 1]" in parsed_final.content
