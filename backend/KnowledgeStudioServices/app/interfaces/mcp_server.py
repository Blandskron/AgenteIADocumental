"""Interoperable read-only MCP JSON-RPC 2.0 server over HTTP authenticated with platform user JWT (STB-07)."""

from __future__ import annotations

import json
from typing import Any

from app.interfaces.mcp_readonly import READ_ONLY_MCP_TOOLS, ReadOnlyMcpDispatcher

MCP_PROTOCOL_VERSION = "2024-11-05"
MAX_MCP_RESULT_LIMIT = 20

MCP_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_documents",
        "description": "Busca documentos autorizados para el usuario autenticado dentro de su empresa activa.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto o palabra clave a buscar."},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_MCP_RESULT_LIMIT, "default": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "get_document_chunks",
        "description": "Obtiene fragmentos autorizados de un documento específico del usuario autenticado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Identificador del documento."},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_MCP_RESULT_LIMIT, "default": 10},
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "list_studio_artifacts",
        "description": "Lista los artefactos de Knowledge Studio propiedad del usuario autenticado.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_MCP_RESULT_LIMIT, "default": 10},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "get_studio_artifact",
        "description": "Recupera un artefacto de Knowledge Studio por su identificador si pertenece al usuario.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string", "description": "Identificador del artefacto."},
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
]


def validate_mcp_origin(origin: str | None, allowed_origins: list[str]) -> bool:
    """Enforces MCP Streamable HTTP Origin validation against DNS rebinding attacks (AG-002)."""
    if not origin or not origin.strip():
        return True  # Non-browser CLI/service clients may omit Origin.
    normalized = origin.strip().rstrip("/").lower()
    allowed = {item.strip().rstrip("/").lower() for item in allowed_origins if item and item.strip()}
    return normalized in allowed


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_mcp_jsonrpc(
    request_payload: dict[str, Any],
    *,
    dispatcher: ReadOnlyMcpDispatcher,
    current_user: dict[str, Any] | None,
) -> dict[str, Any]:
    """Processes a single MCP JSON-RPC 2.0 request strictly under the authenticated user's context."""
    req_id = request_payload.get("id")
    if request_payload.get("jsonrpc") != "2.0" or not isinstance(request_payload.get("method"), str):
        return _jsonrpc_error(req_id, -32600, "Invalid JSON-RPC 2.0 request.")

    if not current_user or not current_user.get("user_id"):
        return _jsonrpc_error(req_id, -32001, "Authentication required for MCP access.")

    method = request_payload["method"]
    params = request_payload.get("params") or {}
    if not isinstance(params, dict):
        return _jsonrpc_error(req_id, -32602, "params must be a JSON object.")

    if method == "initialize":
        return _jsonrpc_result(
            req_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "blandskron-documental-mcp", "version": "1.0.0"},
            },
        )

    if method == "ping":
        return _jsonrpc_result(req_id, {})

    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": MCP_TOOL_DEFINITIONS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(tool_name, str) or tool_name not in READ_ONLY_MCP_TOOLS:
            return _jsonrpc_error(req_id, -32601, f"Tool '{tool_name}' is not allowed (read-only MCP server).")
        if not isinstance(arguments, dict):
            return _jsonrpc_error(req_id, -32602, "Tool arguments must be an object.")

        safe_args = dict(arguments)
        if "limit" in safe_args:
            try:
                safe_args["limit"] = max(1, min(MAX_MCP_RESULT_LIMIT, int(safe_args["limit"])))
            except (TypeError, ValueError):
                safe_args["limit"] = 10

        call_result = dispatcher.invoke(tool_name, safe_args, current_user)
        if not call_result.ok:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps({"error": call_result.error})}],
                    "isError": True,
                },
            )
        return _jsonrpc_result(
            req_id,
            {
                "content": [{"type": "text", "text": json.dumps(call_result.data, default=str, ensure_ascii=False)}],
                "isError": False,
            },
        )

    return _jsonrpc_error(req_id, -32601, f"Method '{method}' not found.")

