"""Tests for EVO-009 (StudioLlmClient) and EVO-010 (MCP search_documents_hybrid)."""

from __future__ import annotations

from app.application.studio_runner import StudioJobRequest
from app.domain.artifacts import ArtifactContent, validate_groundedness
from app.infrastructure.studio_llm_client import StudioLlmClient, _extract_json_object
from app.interfaces.mcp_readonly import READ_ONLY_MCP_TOOLS, ReadOnlyMcpDispatcher


def test_studio_llm_client_deterministic_fallback_passes_groundedness() -> None:
    chunks = {
        ("doc-1", 0): "El contrato establece un plazo maximo de 45 dias habiles para la entrega final.",
    }
    req = StudioJobRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        collection_id="col-1",
        template_id="summary.executive",
        model_id="qwen2.5:3b",
        document_sources=[("doc-1", "sha-1")],
        options={"title": "Resumen Contrato"},
    )
    client = StudioLlmClient()
    raw = client.generate_artifact_json(req, chunks)
    artifact = ArtifactContent.model_validate(raw)
    report = validate_groundedness(artifact, chunks)
    assert report.valid is True
    assert report.score == 1.0


def test_extract_json_object_handles_fenced_blocks() -> None:
    parsed = _extract_json_object('```json\n{"template_id": "summary.executive", "title": "Ok"}\n```')
    assert parsed["template_id"] == "summary.executive"


def test_mcp_dispatcher_supports_search_documents_hybrid_with_audit() -> None:
    assert "search_documents_hybrid" in READ_ONLY_MCP_TOOLS

    dispatcher = ReadOnlyMcpDispatcher(
        {
            "search_documents_hybrid": lambda args, user: {
                "items": [{"document_id": "doc-1", "query": args.get("query"), "tenant": user["active_tenant_id"]}],
                "count": 1,
            }
        }
    )
    res = dispatcher.invoke(
        "search_documents_hybrid",
        {"query": "plazo 45 dias", "limit": 5},
        {"user_id": "u-1", "active_tenant_id": "tenant-a"},
    )
    assert res.ok is True
    assert res.data["count"] == 1
    assert dispatcher.audit_events[-1]["action"] == "mcp.search_documents_hybrid"
