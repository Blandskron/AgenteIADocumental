import base64
import hashlib
import json
from pathlib import Path
import re
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.infrastructure.ai.llm_provider_factory import LLMProviderConfig
from app.infrastructure.database.models import TenantIntegrationModel

KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WEAK_PREFIXES = ("change", "local-", "example", "django-insecure-", "synthetic-example")
ENVELOPE_PREFIX = "secrets1"


@dataclass(frozen=True)
class EffectiveGroqConfig:
    api_key: str
    model: str
    max_tokens: int
    temperature: float
    timeout_seconds: int
    source: str  # "database" | "env" | "not_configured"
    updated_at: datetime | None = None


def _build_keyring(settings: Settings) -> dict[str, Fernet]:
    secret = (settings.secrets_encryption_key or "").strip()
    if not secret:
        secret_file = Path("/run/blandskron-secrets/secrets_encryption_key")
        try:
            if secret_file.is_file():
                secret = secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            secret = ""
    if not secret:
        return {}
    key_id = (settings.secrets_key_id or "v1").strip() or "v1"
    previous: dict[str, str] = {}
    if settings.secrets_previous_keys and settings.secrets_previous_keys.strip():
        try:
            parsed = json.loads(settings.secrets_previous_keys)
            if isinstance(parsed, dict):
                previous = {str(k): str(v) for k, v in parsed.items()}
        except ValueError:
            return {}
    if key_id in previous:
        return {}
    combined = {**previous, key_id: secret}
    if len(combined) > 4:
        return {}
    keyring: dict[str, Fernet] = {}
    for identifier, value in combined.items():
        if (
            not KEY_ID_PATTERN.fullmatch(identifier)
            or len(value) < 32
            or len(set(value)) < 5
            or value.lower().startswith(WEAK_PREFIXES)
        ):
            return {}
        keyring[identifier] = Fernet(base64.urlsafe_b64encode(hashlib.sha256(value.encode("utf-8")).digest()))
    return keyring


def _decrypt_envelope(raw: str | None, keyring: dict[str, Fernet]) -> str | None:
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
    except (InvalidToken, KeyError, ValueError, UnicodeError, AttributeError):
        return None


class GroqConfigResolver:
    """Resolves effective Groq credentials per request with short TTL and updated_at invalidation.

    Precedence:
      1. Active DB row in `tenant_integrations(tenant_id, provider='groq', status='ENABLED')`
      2. Environment fallback (`GROQ_API_KEY` / `GROQ_CHAT_MODEL`)
      3. `not_configured`
    """

    def __init__(self, ttl_seconds: int = 45) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._cache: dict[str, tuple[float, datetime | None, EffectiveGroqConfig]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def resolve(
        self,
        session: Session | None,
        settings: Settings,
        tenant_id: str | None,
    ) -> EffectiveGroqConfig:
        if session is not None and tenant_id:
            row = session.execute(
                select(
                    TenantIntegrationModel.status,
                    TenantIntegrationModel.config,
                    TenantIntegrationModel.secrets_encrypted,
                    TenantIntegrationModel.updated_at,
                ).where(
                    TenantIntegrationModel.tenant_id == tenant_id,
                    TenantIntegrationModel.provider == "groq",
                )
            ).first()
            if row is not None and row.status == "ENABLED" and row.secrets_encrypted:
                now = monotonic()
                cached = self._cache.get(tenant_id)
                if (
                    cached is not None
                    and cached[0] > now
                    and cached[1] == row.updated_at
                ):
                    return cached[2]

                keyring = _build_keyring(settings)
                plaintext = _decrypt_envelope(row.secrets_encrypted, keyring)
                if plaintext and plaintext.strip():
                    cfg = row.config if isinstance(row.config, dict) else {}
                    resolved = EffectiveGroqConfig(
                        api_key=plaintext.strip(),
                        model=str(cfg.get("model") or settings.groq_chat_model),
                        max_tokens=int(cfg.get("max_tokens", settings.chat_completion_max_tokens)),
                        temperature=float(cfg.get("temperature", settings.chat_completion_temperature)),
                        timeout_seconds=int(cfg.get("timeout_seconds", settings.chat_completion_timeout_seconds)),
                        source="database",
                        updated_at=row.updated_at,
                    )
                    if self._ttl_seconds > 0:
                        self._cache[tenant_id] = (now + self._ttl_seconds, row.updated_at, resolved)
                    return resolved
            else:
                self._cache.pop(tenant_id, None)

        if settings.groq_api_key and settings.groq_api_key.strip():
            return EffectiveGroqConfig(
                api_key=settings.groq_api_key.strip(),
                model=settings.groq_chat_model,
                max_tokens=settings.chat_completion_max_tokens,
                temperature=settings.chat_completion_temperature,
                timeout_seconds=settings.chat_completion_timeout_seconds,
                source="env",
            )

        return EffectiveGroqConfig(
            api_key="",
            model=settings.groq_chat_model,
            max_tokens=settings.chat_completion_max_tokens,
            temperature=settings.chat_completion_temperature,
            timeout_seconds=settings.chat_completion_timeout_seconds,
            source="not_configured",
        )

    def resolve_active_provider(
        self,
        session: Session | None,
        settings: Settings,
        tenant_id: str | None,
    ) -> LLMProviderConfig:
        """Resolves whether the tenant uses local Ollama or Groq, falling back to Groq config."""
        if session is not None and tenant_id:
            router_row = session.execute(
                select(TenantIntegrationModel.status, TenantIntegrationModel.config).where(
                    TenantIntegrationModel.tenant_id == tenant_id,
                    TenantIntegrationModel.provider == "ai_router",
                )
            ).first()
            active_provider = (
                ((router_row.config or {}).get("active_provider") if router_row and router_row.status == "ENABLED" else None)
                or "groq"
            )
            if str(active_provider).strip().lower() == "ollama":
                ollama_row = session.execute(
                    select(TenantIntegrationModel.status, TenantIntegrationModel.config).where(
                        TenantIntegrationModel.tenant_id == tenant_id,
                        TenantIntegrationModel.provider == "ollama",
                    )
                ).first()
                cfg = (ollama_row.config if ollama_row and isinstance(ollama_row.config, dict) else {}) or {}
                params = cfg.get("params") if isinstance(cfg.get("params"), dict) else {}
                raw_base = str(cfg.get("base_url") or "http://ollama:11434").strip().rstrip("/")
                openai_base = raw_base if raw_base.endswith("/v1") else f"{raw_base}/v1"
                return LLMProviderConfig(
                    provider="ollama",
                    api_key="ollama-local",
                    model=str(cfg.get("model") or "llama3.2:3b"),
                    base_url=openai_base,
                    max_tokens=int(params.get("max_tokens", settings.chat_completion_max_tokens)),
                    temperature=float(params.get("temperature", settings.chat_completion_temperature)),
                    timeout_seconds=int(params.get("timeout_seconds", 120)),
                    allow_local=True,
                )

        effective_groq = self.resolve(session, settings, tenant_id)
        return LLMProviderConfig(
            provider="groq",
            api_key=effective_groq.api_key,
            model=effective_groq.model,
            max_tokens=effective_groq.max_tokens,
            temperature=effective_groq.temperature,
            timeout_seconds=effective_groq.timeout_seconds,
        )


_default_resolver = GroqConfigResolver()


def get_groq_config_resolver() -> GroqConfigResolver:
    return _default_resolver

