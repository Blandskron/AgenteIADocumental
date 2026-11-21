import os

from app.interfaces.mcp_readonly import ReadOnlyMcpDispatcher


def test_readonly_mcp_enforces_user_auth_tool_allowlist_and_audit():
    dispatcher = ReadOnlyMcpDispatcher({
        "search_documents": lambda args, user: {"query": args.get("q"), "user_id": user["user_id"]},
    })

    # Unauthenticated calls fail closed
    unauth = dispatcher.invoke("search_documents", {"q": "HNSW"}, None)
    assert unauth.ok is False
    assert unauth.error == "AUTHENTICATION_REQUIRED"

    # Unknown / mutating tools are blocked
    blocked = dispatcher.invoke("delete_document", {"id": "1"}, {"user_id": 42})
    assert blocked.ok is False
    assert blocked.error == "TOOL_NOT_ALLOWED"

    # Authorized read-only call succeeds and records mcp.* audit event
    ok = dispatcher.invoke("search_documents", {"q": "HNSW"}, {"user_id": 42, "active_tenant_id": "t1"})
    assert ok.ok is True
    assert ok.data == {"query": "HNSW", "user_id": 42}
    assert dispatcher.audit_events == [{"action": "mcp.search_documents", "actor_user_id": "42", "tenant_id": "t1"}]

    # Registering a mutating tool is forbidden at initialization
    try:
        ReadOnlyMcpDispatcher({"delete_document": lambda *_: None})
        raise AssertionError("Expected ValueError for non-read-only MCP tool")
    except ValueError:
        pass

    assert os.environ.get("STUDIO_ENABLED", "false").lower() != "true"

