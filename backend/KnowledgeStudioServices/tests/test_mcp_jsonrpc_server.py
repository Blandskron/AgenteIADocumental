from __future__ import annotations

import json

from app.interfaces.mcp_readonly import ReadOnlyMcpDispatcher
from app.interfaces.mcp_server import handle_mcp_jsonrpc, validate_mcp_origin


def _make_dispatcher() -> ReadOnlyMcpDispatcher:
    return ReadOnlyMcpDispatcher(
        {
            "search_documents": lambda args, user: {
                "tenant": user["active_tenant_id"],
                "query": args.get("query"),
                "limit": args.get("limit"),
            },
            "get_document_chunks": lambda args, user: {
                "document_id": args.get("document_id"),
                "owner": user["user_id"],
            },
            "list_studio_artifacts": lambda args, user: {"items": [], "owner": user["user_id"]},
            "get_studio_artifact": lambda args, user: {"artifact_id": args.get("artifact_id")},
        }
    )


def test_mcp_jsonrpc_lifecycle_read_only_limits_and_auth() -> None:
    dispatcher = _make_dispatcher()
    user = {"user_id": "u-42", "active_tenant_id": "t-alpha"}

    # Unauthenticated calls fail closed
    unauth = handle_mcp_jsonrpc(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        dispatcher=dispatcher,
        current_user=None,
    )
    assert unauth["error"]["code"] == -32001

    # Initialize
    init = handle_mcp_jsonrpc(
        {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}},
        dispatcher=dispatcher,
        current_user=user,
    )
    assert init["result"]["serverInfo"]["name"] == "blandskron-documental-mcp"

    # List tools exposes exactly the 4 read-only tools
    listed = handle_mcp_jsonrpc(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        dispatcher=dispatcher,
        current_user=user,
    )
    tool_names = {t["name"] for t in listed["result"]["tools"]}
    assert tool_names == {
        "search_documents",
        "get_document_chunks",
        "list_studio_artifacts",
        "get_studio_artifact",
    }
    assert all(t["annotations"]["readOnlyHint"] is True for t in listed["result"]["tools"])

    # Call enforces limit cap <= 20 and records audit
    called = handle_mcp_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "search_documents", "arguments": {"query": "plazo", "limit": 999}},
        },
        dispatcher=dispatcher,
        current_user=user,
    )
    assert called["result"]["isError"] is False
    parsed = json.loads(called["result"]["content"][0]["text"])
    assert parsed["limit"] == 20
    assert parsed["tenant"] == "t-alpha"
    assert dispatcher.audit_events[-1]["action"] == "mcp.search_documents"

    # Rejects any write or unknown tool
    write_attempt = handle_mcp_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "delete_document", "arguments": {"document_id": "d1"}},
        },
        dispatcher=dispatcher,
        current_user=user,
    )
    assert write_attempt["error"]["code"] == -32601


def test_mcp_origin_validation_blocks_dns_rebinding() -> None:
    allowed = ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert validate_mcp_origin(None, allowed) is True
    assert validate_mcp_origin("http://localhost:3000", allowed) is True
    assert validate_mcp_origin("http://127.0.0.1:3000/", allowed) is True
    assert validate_mcp_origin("https://evil.example", allowed) is False
    assert validate_mcp_origin("http://localhost:9999", allowed) is False

