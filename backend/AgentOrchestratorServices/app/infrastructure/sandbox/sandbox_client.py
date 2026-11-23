"""Internal HTTP RPC client for hardened code-sandbox-runner sidecar (AG-010 / AG-011)."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from app.application.tools.registry import redact_secrets

MAX_CODE_BYTES = 8192
FORBIDDEN_CODE_PATTERNS = (
    re.compile(r"\bDeno\.(env|readFile|writeFile|run|Command|open|listen|connect)\b"),
    re.compile(r"\b(fetch|WebSocket|XMLHttpRequest)\s*\("),
    re.compile(r"\bimport\s+.*from\s+['\"]https?://"),
    re.compile(r"\bprocess\.env\b"),
    re.compile(r"\brequire\s*\(\s*['\"](fs|child_process|net|http|https|vm)['\"]\s*\)"),
)


class CodeSandboxValidationError(ValueError):
    """Raised when generated code violates size or static safety policies before hitting the sandbox."""


def validate_sandbox_script(code: str) -> str:
    cleaned = (code or "").strip()
    if not cleaned:
        raise CodeSandboxValidationError("El script de Code Mode está vacío.")
    if len(cleaned.encode("utf-8")) > MAX_CODE_BYTES:
        raise CodeSandboxValidationError(f"El script excede el límite máximo de {MAX_CODE_BYTES} bytes.")
    for pattern in FORBIDDEN_CODE_PATTERNS:
        if pattern.search(cleaned):
            raise CodeSandboxValidationError("El script intenta invocar APIs bloqueadas por la política del sandbox.")
    return cleaned


def strip_credentials_from_data(data: Any) -> Any:
    """Guarantees no JWT, API key, secret envelope or DATABASE_URL ever enters the sandbox."""
    if isinstance(data, str):
        return redact_secrets(data)
    if isinstance(data, list):
        return [strip_credentials_from_data(item) for item in data]
    if isinstance(data, dict):
        safe: dict[str, Any] = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if any(
                forbidden in lowered
                for forbidden in ("token", "jwt", "api_key", "secret", "password", "authorization", "database_url")
            ):
                continue
            safe[str(key)] = strip_credentials_from_data(value)
        return safe
    return data


class SandboxHttpClient:
    """Calls code-sandbox-runner POST /execute over internal Docker network with zero credentials."""

    def __init__(
        self,
        sandbox_url: str = "http://code-sandbox-runner:8090",
        *,
        timeout_ms: int = 5000,
        transport: Any | None = None,
    ) -> None:
        self._sandbox_url = sandbox_url.rstrip("/")
        self._timeout_ms = max(500, min(int(timeout_ms), 10000))
        self._transport = transport

    def execute(self, *, code: str, data: dict[str, Any]) -> dict[str, Any]:
        validated_code = validate_sandbox_script(code)
        sanitized_data = strip_credentials_from_data(data)
        payload = {
            "code": validated_code,
            "data": sanitized_data,
            "timeout_ms": self._timeout_ms,
        }
        url = f"{self._sandbox_url}/execute"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        internal_token = (os.environ.get("SANDBOX_INTERNAL_TOKEN") or "").strip()
        if internal_token:
            headers["X-Sandbox-Token"] = internal_token
        timeout_sec = (self._timeout_ms / 1000.0) + 2.0

        if self._transport is not None:
            result = self._transport(url, payload, headers, timeout_sec)
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(redact_secrets(f"Sandbox execution failed: {exc}")) from None

        if not isinstance(result, dict):
            raise RuntimeError("Invalid response from code-sandbox-runner.")
        if not result.get("ok"):
            raise RuntimeError(redact_secrets(str(result.get("error") or "Sandbox execution error.")))
        return {
            "ok": True,
            "output": result.get("output"),
            "stdout": redact_secrets(str(result.get("stdout") or ""))[:4000],
            "duration_ms": int(result.get("duration_ms") or 0),
        }
