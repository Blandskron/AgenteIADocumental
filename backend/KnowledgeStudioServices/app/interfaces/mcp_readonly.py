"""Read-only MCP tool router authenticated strictly with the user's platform JWT context (R6-05)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

READ_ONLY_MCP_TOOLS = frozenset(
    {
        "search_documents",
        "search_documents_hybrid",
        "get_document_chunks",
        "list_studio_artifacts",
        "get_studio_artifact",
    }
)


@dataclass(frozen=True)
class McpCallResult:
    tool: str
    ok: bool
    data: Any = None
    error: str | None = None


class ReadOnlyMcpDispatcher:
    """Dispatches read-only MCP tool calls enforcing platform user authentication and audit prefixes."""

    def __init__(self, handlers: dict[str, Callable[[dict[str, Any], dict[str, Any]], Any]]) -> None:
        invalid = set(handlers) - READ_ONLY_MCP_TOOLS
        if invalid:
            raise ValueError(f"Non-read-only MCP tools are forbidden: {sorted(invalid)}")
        self._handlers = handlers
        self.audit_events: list[dict[str, Any]] = []

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        current_user: dict[str, Any] | None,
    ) -> McpCallResult:
        if not current_user or not current_user.get("user_id"):
            return McpCallResult(tool=tool_name, ok=False, error="AUTHENTICATION_REQUIRED")
        if tool_name not in READ_ONLY_MCP_TOOLS or tool_name not in self._handlers:
            return McpCallResult(tool=tool_name, ok=False, error="TOOL_NOT_ALLOWED")

        data = self._handlers[tool_name](arguments or {}, current_user)
        self.audit_events.append({
            "action": f"mcp.{tool_name}",
            "actor_user_id": str(current_user["user_id"]),
            "tenant_id": current_user.get("active_tenant_id"),
        })
        return McpCallResult(tool=tool_name, ok=True, data=data)

