"""Live AuthServices /api/users/me/ identity verification with short TTL cache (AG-017)."""

from __future__ import annotations

import hashlib
import json
from time import monotonic
from typing import Any
import urllib.error
import urllib.request

from app.application.tools.registry import redact_secrets


class IdentityUnauthorizedError(PermissionError):
    """Raised when AuthServices rejects a revoked, expired or disabled account (HTTP 401/403)."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class IdentityServiceUnavailableError(RuntimeError):
    """Raised when AUTH_IDENTITY_URL is configured but AuthServices cannot be reached (HTTP 503)."""


class LiveIdentityVerifier:
    """Verifies active account status and current tenant against AuthServices /api/users/me/."""

    def __init__(self, *, ttl_seconds: float = 10.0, transport: Any | None = None) -> None:
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._transport = transport
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def verify(self, *, raw_token: str, auth_identity_url: str) -> dict[str, Any]:
        url = (auth_identity_url or "").strip()
        if not url:
            return {}
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = monotonic()
        cached = self._cache.get(token_hash)
        if cached is not None and cached[0] > now:
            return dict(cached[1])

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Accept": "application/json",
        }
        try:
            if self._transport is not None:
                status_code, body = self._transport(url, headers, 5.0)
            else:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    status_code = int(resp.status)
                    body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise IdentityUnauthorizedError(
                    exc.code,
                    "La sesión fue revocada o la cuenta está deshabilitada en AuthServices.",
                ) from None
            raise IdentityServiceUnavailableError(
                redact_secrets(f"AuthServices devolvió HTTP {exc.code}.")
            ) from None
        except Exception as exc:
            raise IdentityServiceUnavailableError(
                redact_secrets(f"No se pudo verificar la identidad vigente en AuthServices: {exc}")
            ) from None

        if status_code in (401, 403):
            raise IdentityUnauthorizedError(
                status_code,
                "La sesión fue revocada o la cuenta está deshabilitada en AuthServices.",
            )
        if status_code >= 500 or not isinstance(body, dict):
            raise IdentityServiceUnavailableError("AuthServices no está disponible para verificar la identidad.")
        if body.get("is_active") is False:
            raise IdentityUnauthorizedError(403, "Cuenta deshabilitada.")

        resolved = {
            "user_id": str(body.get("id") or body.get("user_id") or ""),
            "active_tenant_id": str(body.get("active_tenant_id") or body.get("tenant_id") or ""),
            "is_superuser": bool(body.get("is_superuser") or body.get("is_superadmin")),
            "permissions": list(body.get("permissions") or []),
        }
        if self._ttl_seconds > 0:
            self._cache[token_hash] = (now + self._ttl_seconds, resolved)
        return resolved


_default_verifier = LiveIdentityVerifier()


def get_default_identity_verifier() -> LiveIdentityVerifier:
    return _default_verifier
