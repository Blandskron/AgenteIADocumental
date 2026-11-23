"""HTTP JSON-RPC 2.0 client adapter for KnowledgeStudioServices MCP with JWT propagation (AG-005)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from app.application.tools.registry import (
    ToolPolicy,
    ToolRegistry,
    ToolSpec,
    redact_secrets,
)

DEFAULT_MCP_TOOLS = (
    (
        "search_documents",
        "Busca documentos autorizados del usuario autenticado.",
        {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
    ),
    (
        "search_documents_hybrid",
        "Recupera fragmentos relevantes mediante búsqueda híbrida (FTS + coincidencia) respetando aislamiento del tenant.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "document_ids": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    ),
    (
        "get_document_chunks",
        "Obtiene fragmentos autorizados de un documento específico.",
        {"type": "object", "properties": {"document_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["document_id"]},
    ),
    (
        "list_studio_artifacts",
        "Lista artefactos de Knowledge Studio propiedad del usuario.",
        {"type": "object", "properties": {"limit": {"type": "integer"}}},
    ),
    (
        "get_studio_artifact",
        "Obtiene un artefacto de Knowledge Studio por ID.",
        {"type": "object", "properties": {"artifact_id": {"type": "string"}}, "required": ["artifact_id"]},
    ),
)


class McpHttpClient:
    """Calls KnowledgeStudioServices POST /api/v1/mcp strictly propagating the platform user's JWT."""

    def __init__(
        self,
        mcp_url: str,
        *,
        timeout_seconds: float = 10.0,
        transport: Any | None = None,
    ) -> None:
        self._mcp_url = mcp_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def call_tool(self, tool_name: str, arguments: dict[str, Any], user_jwt: str) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("Missing user JWT for MCP propagation.")
        payload = {
            "jsonrpc": "2.0",
            "id": f"ag-{tool_name}",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {
            "Authorization": f"Bearer {user_jwt.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._transport is not None:
            response_body = self._transport(self._mcp_url, payload, headers, self._timeout)
        else:
            req = urllib.request.Request(
                self._mcp_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    response_body = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(redact_secrets(f"MCP call failed: {exc}")) from None

        if "error" in response_body:
            raise RuntimeError(redact_secrets(str(response_body["error"].get("message") or "MCP error")))

        result = response_body.get("result") or {}
        if result.get("isError"):
            raise RuntimeError("MCP tool returned an error result.")
        content = result.get("content") or []
        if content and isinstance(content[0], dict) and isinstance(content[0].get("text"), str):
            try:
                return json.loads(content[0]["text"])
            except ValueError:
                return {"text": content[0]["text"]}
        return result


def register_default_mcp_tools(registry: ToolRegistry, mcp_client: McpHttpClient) -> None:
    """Registers the 4 read-only MCP tools in the central ToolRegistry without duplicating MCP logic."""
    for name, description, schema in DEFAULT_MCP_TOOLS:
        def _make_handler(tool_name: str):
            def _handler(args: dict[str, Any], user: dict[str, Any]) -> Any:
                return mcp_client.call_tool(tool_name, args, str(user.get("raw_token") or ""))
            return _handler

        registry.register(
            ToolSpec(
                name=name,
                description=description,
                input_schema=schema,
                policy=ToolPolicy(read_only=True, requires_human_approval=False, max_results=20),
                handler=_make_handler(name),
            )
        )

