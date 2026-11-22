"""Tenant-aware LLM adapter reusing AuthServices/RagDocumentChatServices ai_router (AG-006).

Supports Groq, local Ollama and OpenAI-compatible endpoints with:
- SSRF validation (`validate_provider_base_url`)
- `secrets1.<key_id>.<fernet>` envelope decryption
- Optional `langchain-core` / `langchain-groq` / `langchain-ollama` / `langchain-openai` binding
- Structured JSON fallback when small local Ollama models (2b/3b) do not emit native tool calls
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.application.tools.registry import redact_secrets

KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WEAK_PREFIXES = ("change", "local-", "example", "django-insecure-", "synthetic-example")
ENVELOPE_PREFIX = "secrets1"
ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "ollama", "host.docker.internal"}


class LLMConfigurationError(RuntimeError):
    """Raised when no valid LLM provider is configured for the tenant."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LLMProviderError(RuntimeError):
    """Raised when an upstream LLM provider fails or returns an invalid payload."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(redact_secrets(message))
        self.code = code


@dataclass(frozen=True)
class ResolvedLLMConfig:
    provider: str  # "groq" | "ollama" | "openai_compatible"
    api_key: str
    model: str
    base_url: str = ""
    max_tokens: int = 2000
    temperature: float = 0.2
    timeout_seconds: int = 60
    allow_local: bool = False
    source: str = "database"  # "database" | "env" | "not_configured"


@dataclass(frozen=True)
class AgentLLMResponse:
    action: str  # "tool_call" | "final" | "request_approval"
    content: str = ""
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    approval_action: str | None = None
    approval_summary: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    used_json_fallback: bool = False


def validate_provider_base_url(base_url: str, *, allow_local: bool = False) -> str:
    """Enforces SSRF protections on custom LLM provider base URLs."""
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        raise LLMConfigurationError("invalid_base_url", "URL base de proveedor LLM vacía.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise LLMConfigurationError("ssrf_blocked", "Solo se permiten esquemas http/https para proveedores LLM.")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise LLMConfigurationError("ssrf_blocked", "Host de proveedor LLM inválido.")

    if not allow_local and parsed.scheme != "https":
        raise LLMConfigurationError("ssrf_blocked", "Proveedores externos requieren HTTPS.")

    if host in ALLOWED_LOCAL_HOSTS:
        if not allow_local:
            raise LLMConfigurationError("ssrf_blocked", f"Host local bloqueado para proveedor externo: {host}")
        return cleaned

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise LLMConfigurationError("ssrf_blocked", f"Dirección IP bloqueada por política SSRF: {host}")
        if (ip.is_private or ip.is_loopback) and not allow_local:
            raise LLMConfigurationError("ssrf_blocked", f"Dirección privada/loopback bloqueada: {host}")

    if host.endswith(".internal") or host == "metadata.google.internal":
        raise LLMConfigurationError("ssrf_blocked", f"Host interno bloqueado por política SSRF: {host}")

    return cleaned


def build_secrets_keyring(
    encryption_key: str | None = None,
    key_id: str | None = None,
    previous_keys_json: str | None = None,
) -> dict[str, Any]:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return {}
    secret = (encryption_key if encryption_key is not None else os.environ.get("SECRETS_ENCRYPTION_KEY", "")).strip()
    if not secret:
        secret_file = Path("/run/blandskron-secrets/secrets_encryption_key")
        try:
            if secret_file.is_file():
                secret = secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            secret = ""
    if not secret:
        return {}
    resolved_key_id = (key_id if key_id is not None else os.environ.get("SECRETS_KEY_ID", "v1")).strip() or "v1"
    previous: dict[str, str] = {}
    raw_prev = previous_keys_json if previous_keys_json is not None else os.environ.get("SECRETS_PREVIOUS_KEYS", "")
    if raw_prev and raw_prev.strip():
        try:
            parsed = json.loads(raw_prev)
            if isinstance(parsed, dict):
                previous = {str(k): str(v) for k, v in parsed.items()}
        except ValueError:
            return {}
    if resolved_key_id in previous:
        return {}
    combined = {**previous, resolved_key_id: secret}
    if len(combined) > 4:
        return {}

    keyring: dict[str, Any] = {}
    for identifier, value in combined.items():
        if (
            not KEY_ID_PATTERN.fullmatch(identifier)
            or len(value) < 32
            or len(set(value)) < 5
            or value.lower().startswith(WEAK_PREFIXES)
        ):
            return {}
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        keyring[identifier] = Fernet(base64.urlsafe_b64encode(digest))
    return keyring


def decrypt_secrets_envelope(raw: str | None, keyring: dict[str, Any]) -> str | None:
    if not raw or not keyring:
        return None
    envelope = raw
    if not envelope.startswith(f"{ENVELOPE_PREFIX}."):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("api_key"), str):
                envelope = parsed["api_key"]
            else:
                return None
        except ValueError:
            return None
    if not envelope.startswith(f"{ENVELOPE_PREFIX}."):
        return None
    try:
        _, identifier, ciphertext = envelope.split(".", 2)
        return keyring[identifier].decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        return None


class TenantLLMConfigResolver:
    """Resolves active provider (ai_router -> groq / ollama / openai_compatible) per tenant without restart."""

    def __init__(
        self,
        *,
        row_loader: Any | None = None,
        encryption_key: str | None = None,
        key_id: str | None = None,
        previous_keys_json: str | None = None,
    ) -> None:
        self._row_loader = row_loader
        self._encryption_key = encryption_key
        self._key_id = key_id
        self._previous_keys_json = previous_keys_json

    def _load_integration(self, tenant_id: str, provider: str) -> dict[str, Any] | None:
        if self._row_loader is not None:
            return self._row_loader(tenant_id, provider)
        return None

    def resolve(self, tenant_id: str) -> ResolvedLLMConfig:
        router = self._load_integration(tenant_id, "ai_router")
        active = "groq"
        if router and router.get("status") == "ENABLED":
            cfg = router.get("config") or {}
            active = str(cfg.get("active_provider") or "groq").strip().lower()

        if active == "ollama":
            ollama_row = self._load_integration(tenant_id, "ollama")
            cfg = (ollama_row.get("config") if ollama_row and isinstance(ollama_row.get("config"), dict) else {}) or {}
            params = cfg.get("params") if isinstance(cfg.get("params"), dict) else {}
            raw_base = str(cfg.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")).strip().rstrip("/")
            openai_base = raw_base if raw_base.endswith("/v1") else f"{raw_base}/v1"
            validated_url = validate_provider_base_url(openai_base, allow_local=True)
            return ResolvedLLMConfig(
                provider="ollama",
                api_key="ollama-local",
                model=str(cfg.get("model") or "qwen2.5:3b"),
                base_url=validated_url,
                max_tokens=int(params.get("max_tokens", 2000)),
                temperature=float(params.get("temperature", 0.2)),
                timeout_seconds=int(params.get("timeout_seconds", 120)),
                allow_local=True,
                source="database" if ollama_row else "env",
            )

        if active == "openai_compatible":
            row = self._load_integration(tenant_id, "openai_compatible")
            if row and row.get("status") == "ENABLED":
                cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
                keyring = build_secrets_keyring(self._encryption_key, self._key_id, self._previous_keys_json)
                api_key = decrypt_secrets_envelope(row.get("secrets_encrypted"), keyring) or ""
                base_url = validate_provider_base_url(
                    str(cfg.get("base_url") or ""),
                    allow_local=bool(cfg.get("allow_local", False)),
                )
                return ResolvedLLMConfig(
                    provider="openai_compatible",
                    api_key=api_key.strip(),
                    model=str(cfg.get("model") or "gpt-4o-mini"),
                    base_url=base_url,
                    max_tokens=int(cfg.get("max_tokens", 2000)),
                    temperature=float(cfg.get("temperature", 0.2)),
                    timeout_seconds=int(cfg.get("timeout_seconds", 60)),
                    allow_local=bool(cfg.get("allow_local", False)),
                    source="database",
                )

        groq_row = self._load_integration(tenant_id, "groq")
        if groq_row and groq_row.get("status") == "ENABLED" and groq_row.get("secrets_encrypted"):
            keyring = build_secrets_keyring(self._encryption_key, self._key_id, self._previous_keys_json)
            plaintext = decrypt_secrets_envelope(groq_row.get("secrets_encrypted"), keyring)
            if plaintext and plaintext.strip():
                cfg = groq_row.get("config") if isinstance(groq_row.get("config"), dict) else {}
                return ResolvedLLMConfig(
                    provider="groq",
                    api_key=plaintext.strip(),
                    model=str(cfg.get("model") or os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")),
                    base_url="https://api.groq.com/openai/v1",
                    max_tokens=int(cfg.get("max_tokens", 2000)),
                    temperature=float(cfg.get("temperature", 0.2)),
                    timeout_seconds=int(cfg.get("timeout_seconds", 60)),
                    allow_local=False,
                    source="database",
                )

        env_key = os.environ.get("GROQ_API_KEY", "").strip()
        if env_key:
            return ResolvedLLMConfig(
                provider="groq",
                api_key=env_key,
                model=os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile"),
                base_url="https://api.groq.com/openai/v1",
                max_tokens=2000,
                temperature=0.2,
                timeout_seconds=60,
                allow_local=False,
                source="env",
            )

        return ResolvedLLMConfig(
            provider="groq",
            api_key="",
            model=os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile"),
            base_url="https://api.groq.com/openai/v1",
            source="not_configured",
        )


def parse_structured_json_fallback(raw_text: str) -> AgentLLMResponse | None:
    """Extracts a structured JSON action from small Ollama models that do not emit native tool_calls."""
    text = (raw_text or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    if not candidate.startswith("{"):
        brace_match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not brace_match:
            return None
        candidate = brace_match.group(0)
    try:
        parsed = json.loads(candidate)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None

    action = str(parsed.get("action") or "").strip().lower()
    if action == "tool_call" and isinstance(parsed.get("name"), str):
        args = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else {}
        return AgentLLMResponse(
            action="tool_call",
            tool_name=parsed["name"].strip(),
            tool_arguments=args,
            used_json_fallback=True,
        )
    if action == "request_approval" and isinstance(parsed.get("approval_action"), str):
        return AgentLLMResponse(
            action="request_approval",
            approval_action=parsed["approval_action"].strip(),
            approval_summary=str(parsed.get("summary") or "Aprobación humana requerida."),
            content=str(parsed.get("content") or ""),
            used_json_fallback=True,
        )
    if action == "final" and isinstance(parsed.get("answer"), str):
        return AgentLLMResponse(
            action="final",
            content=parsed["answer"].strip(),
            used_json_fallback=True,
        )
    return None


class AgentModelClient:
    """Unified chat/tool-calling client supporting Groq, Ollama and OpenAI-compatible endpoints."""

    def __init__(self, config: ResolvedLLMConfig, *, transport: Any | None = None) -> None:
        if config.source == "not_configured" or (config.provider != "ollama" and not config.api_key):
            raise LLMConfigurationError(
                "not_configured",
                "No hay un proveedor de IA configurado para este tenant. Configura Groq u Ollama en /settings/ai.",
            )
        if config.base_url:
            validate_provider_base_url(config.base_url, allow_local=config.allow_local)
        self.config = config
        self._transport = transport

    def _endpoint_url(self) -> str:
        base = self.config.base_url.rstrip("/") if self.config.base_url else "https://api.groq.com/openai/v1"
        return f"{base}/chat/completions"

    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> AgentLLMResponse:
        effective_max = min(int(max_tokens or self.config.max_tokens), self.config.max_tokens)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": effective_max,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = self._endpoint_url()

        if self._transport is not None:
            raw_response = self._transport(url, payload, headers, self.config.timeout_seconds)
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    raw_response = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise LLMProviderError("provider_error", f"Fallo al invocar {self.config.provider}: {exc}") from None

        return self._parse_response(raw_response)

    def _parse_response(self, raw_response: dict[str, Any]) -> AgentLLMResponse:
        if not isinstance(raw_response, dict):
            raise LLMProviderError("provider_error", "Respuesta inválida del proveedor LLM.")
        choices = raw_response.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise LLMProviderError("provider_error", "El proveedor LLM no devolvió opciones válidas.")

        usage = raw_response.get("usage") if isinstance(raw_response.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)

        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if tool_calls and isinstance(tool_calls[0], dict):
            fn = tool_calls[0].get("function") or {}
            name = str(fn.get("name") or "").strip()
            raw_args = fn.get("arguments")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except ValueError:
                    parsed_args = {}
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}
            if name:
                return AgentLLMResponse(
                    action="tool_call",
                    tool_name=name,
                    tool_arguments=parsed_args,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

        content = str(message.get("content") or "").strip()
        fallback = parse_structured_json_fallback(content)
        if fallback is not None:
            return AgentLLMResponse(
                action=fallback.action,
                content=fallback.content,
                tool_name=fallback.tool_name,
                tool_arguments=fallback.tool_arguments,
                approval_action=fallback.approval_action,
                approval_summary=fallback.approval_summary,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                used_json_fallback=True,
            )

        return AgentLLMResponse(
            action="final",
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def build_agent_model_client(
    config: ResolvedLLMConfig,
    *,
    transport: Any | None = None,
) -> AgentModelClient:
    return AgentModelClient(config, transport=transport)
