from __future__ import annotations

import pytest

from app.infrastructure.ai.llm_provider_factory import LLMProviderConfig, build_llm_provider
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.infrastructure.ai.llm_provider_openai_compatible import OpenAICompatibleLLMProvider


def test_factory_builds_groq_provider_by_default() -> None:
    provider = build_llm_provider(
        LLMProviderConfig(provider="groq", api_key="", model="openai/gpt-oss-20b")
    )
    assert isinstance(provider, GroqLLMProvider)
    assert not isinstance(provider, OpenAICompatibleLLMProvider)


def test_factory_builds_openai_compatible_and_enforces_ssrf() -> None:
    provider = build_llm_provider(
        LLMProviderConfig(
            provider="openai_compatible",
            api_key="",
            model="gpt-4o-mini",
            base_url="https://api.example.com/v1",
        )
    )
    assert isinstance(provider, OpenAICompatibleLLMProvider)

    with pytest.raises(ValueError, match="SSRF"):
        build_llm_provider(
            LLMProviderConfig(
                provider="openai_compatible",
                api_key="",
                model="gpt-4o-mini",
                base_url="https://169.254.169.254/v1",
            )
        )


def test_factory_builds_local_ollama_provider() -> None:
    provider = build_llm_provider(
        LLMProviderConfig(
            provider="ollama",
            api_key="",
            model="llama3.2",
        )
    )
    assert isinstance(provider, OpenAICompatibleLLMProvider)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        build_llm_provider(
            LLMProviderConfig(provider="unknown_vendor", api_key="", model="m1")
        )

