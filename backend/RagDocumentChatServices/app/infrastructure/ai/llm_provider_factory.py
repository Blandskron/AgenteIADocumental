"""Unified LLM provider factory routing Groq, OpenAI-compatible and local Ollama (R8-08)."""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.infrastructure.ai.llm_provider_openai_compatible import OpenAICompatibleLLMProvider


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str  # "groq" | "openai_compatible" | "ollama"
    api_key: str
    model: str
    base_url: str = ""
    max_tokens: int = 2000
    temperature: float = 0.3
    timeout_seconds: int = 60
    allow_local: bool = False


def build_llm_provider(config: LLMProviderConfig) -> GroqLLMProvider:
    """Instantiates the requested LLM provider enforcing SSRF policies for custom endpoints."""
    provider_name = (config.provider or "groq").strip().lower()
    if provider_name == "groq":
        return GroqLLMProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
        )
    if provider_name == "ollama":
        base_url = config.base_url.strip() or "http://127.0.0.1:11434/v1"
        return OpenAICompatibleLLMProvider(
            api_key=config.api_key or "ollama-local",
            model=config.model,
            base_url=base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            allow_local=True,
        )
    if provider_name == "openai_compatible":
        return OpenAICompatibleLLMProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            allow_local=config.allow_local,
        )
    raise ValueError(f"Proveedor LLM no soportado: {config.provider}")

