from __future__ import annotations

from app.application.graph.code_mode_node import (
    describe_readonly_tool,
    discover_readonly_tools,
)
from app.application.tools.registry import ToolPolicy, ToolRegistry, ToolSpec
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools
from app.infrastructure.search.search_client import (
    DocumentSearchHttpClient,
    register_document_search_tools,
)


def test_progressive_discovery_exposes_only_readonly_tools_and_full_schemas() -> None:
    registry = ToolRegistry()
    register_default_mcp_tools(registry, McpHttpClient("http://knowledge-studio-service:8000/api/v1/mcp"))
    register_document_search_tools(registry, DocumentSearchHttpClient("http://document-search-service:8000"))
    # Register a write tool requiring human approval -> must NOT be exposed by read-only progressive discovery
    registry.register(
        ToolSpec(
            name="save_studio_artifact",
            description="Guarda artefacto tras aprobación humana",
            input_schema={"type": "object", "properties": {}},
            policy=ToolPolicy(read_only=False, requires_human_approval=True),
            handler=lambda _a, _u: None,
        )
    )

    all_ro = discover_readonly_tools(registry, "")
    ro_names = {t["name"] for t in all_ro}
    assert "search_documents" in ro_names
    assert "search_documents_fts" in ro_names
    assert "save_studio_artifact" not in ro_names

    assert describe_readonly_tool(registry, "save_studio_artifact") is None
    fts_schema = describe_readonly_tool(registry, "search_documents_fts")
    assert fts_schema is not None
    assert fts_schema["input_schema"]["required"] == ["query"]
