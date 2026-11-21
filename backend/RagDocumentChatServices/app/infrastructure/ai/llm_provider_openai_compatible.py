"""OpenAI-compatible LLM provider adapter with strict anti-SSRF base_url allowlist (R6-03)."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from app.domain.chat import ChatMessage
from app.domain.embeddings import SearchResult
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.shared.errors import ExternalServiceError


def validate_provider_base_url(base_url: str, *, allow_local: bool = False) -> str:
    """Validates a custom OpenAI-compatible base_url against SSRF (blocks RFC1918/loopback/link-local/metadata)."""
    raw = (base_url or "").strip().rstrip("/")
    parsed = urlsplit(raw)
    if not parsed.hostname:
        raise ValueError("Provider base_url must include a valid hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Provider base_url must not contain embedded credentials.")
    if parsed.scheme not in (("https", "http") if allow_local else ("https",)):
        raise ValueError("Provider base_url must use HTTPS.")

    host = parsed.hostname.lower()
    if not allow_local:
        if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
            raise ValueError("Local or internal hostnames are blocked by SSRF policy.")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise ValueError("Private, loopback, or link-local IP addresses are blocked by SSRF policy.")
        except ValueError as exc:
            if "blocked by SSRF" in str(exc):
                raise
    return raw


class OpenAICompatibleLLMProvider(GroqLLMProvider):
    """Reuses the hardened prompt/citation pipeline of GroqLLMProvider against any SSRF-validated endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        timeout_seconds: int = 60,
        allow_local: bool = False,
    ) -> None:
        validated_url = validate_provider_base_url(base_url, allow_local=allow_local)
        self._client = (
            OpenAI(
                api_key=api_key,
                base_url=validated_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
            if api_key.strip()
            else None
        )
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._base_url = validated_url

    def answer_with_context(
        self,
        question: str,
        context: list[SearchResult],
        history: list[ChatMessage] | None = None,
        mode: str = "qa",
    ) -> str:
        try:
            return super().answer_with_context(question, context, history=history, mode=mode)
        except (APITimeoutError, AuthenticationError, RateLimitError, APIError) as exc:
            raise ExternalServiceError("Error al consultar el proveedor OpenAI-compatible.") from exc

