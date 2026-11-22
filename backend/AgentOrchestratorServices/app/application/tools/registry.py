"""Typed read-only ToolRegistry with capability policies and secret redaction (AG-005)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

MAX_TOOL_LIMIT = 20
SECRET_REDACT_RE = re.compile(r"(Bearer\s+[A-Za-z0-9._-]+|secrets1\.[A-Za-z0-9._-]+|gsk_[A-Za-z0-9]+)", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    return SECRET_REDACT_RE.sub("[REDACTED]", text or "")


@dataclass(frozen=True)
class ToolPolicy:
    read_only: bool = True
    requires_human_approval: bool = False
    max_results: int = MAX_TOOL_LIMIT
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    policy: ToolPolicy
    handler: Callable[[dict[str, Any], dict[str, Any]], Any]


class ToolPermissionError(PermissionError):
    """Raised when a tool violates read-only policy or is outside the allowlist."""


class ToolRegistry:
    """Central allowlisted catalog of agent tools with enforced read-only boundaries."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.policy.read_only and not spec.policy.requires_human_approval:
            raise ToolPermissionError(
                f"Write tool '{spec.name}' must explicitly require human approval."
            )
        self._tools[spec.name] = spec

    def list_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "read_only": spec.policy.read_only,
                "requires_human_approval": spec.policy.requires_human_approval,
                "max_results": spec.policy.max_results,
            }
            for spec in self._tools.values()
        ]

    def invoke(self, name: str, arguments: dict[str, Any], user_context: dict[str, Any]) -> Any:
        if not user_context or not user_context.get("user_id"):
            raise ToolPermissionError("User authentication context is required.")
        spec = self._tools.get(name)
        if spec is None:
            raise ToolPermissionError(f"Tool '{name}' is not registered in the allowlist.")
        if not spec.policy.read_only:
            raise ToolPermissionError(f"Tool '{name}' requires explicit human approval before execution.")

        safe_args = dict(arguments or {})
        required_fields = spec.input_schema.get("required") or []
        for field_name in required_fields:
            if field_name not in safe_args or safe_args[field_name] in (None, ""):
                raise ValueError(f"Tool '{name}' missing required argument '{field_name}'.")
        if "limit" in safe_args:
            try:
                safe_args["limit"] = max(1, min(spec.policy.max_results, int(safe_args["limit"])))
            except (TypeError, ValueError):
                safe_args["limit"] = min(10, spec.policy.max_results)

        try:
            return spec.handler(safe_args, user_context)
        except Exception as exc:
            raise RuntimeError(redact_secrets(str(exc))) from None

