from __future__ import annotations

import json

from app.application.tools.registry import (
    ToolPermissionError,
    ToolPolicy,
    ToolRegistry,
    ToolSpec,
    redact_secrets,
)
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools


def test_tool_registry_enforces_allowlist_limit_cap_and_secret_redaction() -> None:
    captured: list[dict] = []

    def fake_transport(url, payload, headers, _timeout):
        captured.append({"url": url, "payload": payload, "headers": headers})
        return {
            "jsonrpc": "2.0",
            "id": payload["id"],
            "result": {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"items": [], "limit": payload["params"]["arguments"].get("limit")}),
                    }
                ],
            },
        }

    registry = ToolRegistry()
    client = McpHttpClient("http://knowledge-studio-service:8000/api/v1/mcp", transport=fake_transport)
    register_default_mcp_tools(registry, client)

    names = {t["name"] for t in registry.list_specs()}
    assert names == {"search_documents", "get_document_chunks", "list_studio_artifacts", "get_studio_artifact"}

    user = {"user_id": "42", "active_tenant_id": "t1", "raw_token": "synthetic.jwt.token"}
    result = registry.invoke("search_documents", {"query": "plazo", "limit": 500}, user)
    assert result["limit"] == 20
    assert captured[0]["headers"]["Authorization"] == "Bearer synthetic.jwt.token"

    # Rejects unknown tool
    try:
        registry.invoke("delete_everything", {}, user)
        raise AssertionError("Expected ToolPermissionError")
    except ToolPermissionError:
        pass

    # Rejects registering write tool without human approval
    try:
        registry.register(
            ToolSpec(
                name="unsafe_write",
                description="bad",
                input_schema={},
                policy=ToolPolicy(read_only=False, requires_human_approval=False),
                handler=lambda a, u: None,
            )
        )
        raise AssertionError("Expected ToolPermissionError")
    except ToolPermissionError:
        pass

    assert "[REDACTED]" in redact_secrets("Error with Bearer secret.jwt.123 and secrets1.v1.abc")
    assert "secret.jwt.123" not in redact_secrets("Error with Bearer secret.jwt.123")

