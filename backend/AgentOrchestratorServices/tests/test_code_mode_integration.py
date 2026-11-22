from __future__ import annotations

import json

import pytest
from app.application.graph.code_mode_node import (
    CodeModeDisabledError,
    describe_readonly_tool,
    discover_readonly_tools,
    execute_code_mode_node,
)
from app.application.graph.research_graph import ResearchAgentGraph
from app.application.quota_service import TenantQuotaService
from app.application.tools.registry import ToolRegistry
from app.infrastructure.database.audit_logger import AuditLogger
from app.infrastructure.database.checkpointer import InMemoryCheckpointer
from app.infrastructure.database.runs_repository import InMemoryRunsRepository
from app.infrastructure.llm.model_factory import (
    ResolvedLLMConfig,
    build_agent_model_client,
)
from app.infrastructure.mcp.mcp_client import McpHttpClient, register_default_mcp_tools
from app.infrastructure.sandbox.sandbox_client import (
    CodeSandboxValidationError,
    SandboxHttpClient,
    strip_credentials_from_data,
    validate_sandbox_script,
)


def test_code_mode_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODE_MODE_ENABLED", "false")
    sandbox = SandboxHttpClient(transport=lambda *_a: {"ok": True, "output": 1})
    with pytest.raises(CodeModeDisabledError):
        execute_code_mode_node(
            code="export default (data) => data.evidence.length;",
            evidence=[],
            sandbox_client=sandbox,
            audit_logger=AuditLogger(),
            tenant_id="t-1",
            actor_user_id="u-1",
            run_id="run-1",
        )


def test_progressive_discovery_and_credential_stripping() -> None:
    registry = ToolRegistry()
    register_default_mcp_tools(registry, McpHttpClient("http://knowledge-studio-service:8000/api/v1/mcp"))

    found = discover_readonly_tools(registry, "documento")
    assert any(t["name"] == "search_documents" for t in found)
    schema = describe_readonly_tool(registry, "get_document_chunks")
    assert schema is not None
    assert "document_id" in schema["input_schema"]["properties"]

    cleaned = strip_credentials_from_data(
        {
            "raw_token": "Bearer secret.jwt.123",
            "api_key": "gsk_123456",
            "database_url": "postgresql://user:pass@postgres/db",
            "quote": "Monto USD 5000 (Bearer leaked.token.999)",
        }
    )
    assert "raw_token" not in cleaned
    assert "api_key" not in cleaned
    assert "database_url" not in cleaned
    assert "[REDACTED]" in cleaned["quote"]

    with pytest.raises(CodeSandboxValidationError):
        validate_sandbox_script("const x = await fetch('https://evil.example.com');")


def test_code_mode_end_to_end_comparative_table_and_expiration_calc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODE_MODE_ENABLED", "true")
    sandbox_payloads: list[dict] = []

    def fake_sandbox_transport(_url, payload, _headers, _timeout):
        sandbox_payloads.append(payload)
        return {
            "ok": True,
            "output": {"total_amount": 25000, "contracts_expiring_2027": 1},
            "stdout": "",
            "duration_ms": 42,
        }

    turn = {"n": 0}

    def fake_llm(_url, _payload, _headers, _timeout):
        turn["n"] += 1
        if turn["n"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "execute_code",
                                        "arguments": json.dumps(
                                            {"code": "export default (data) => ({ total_amount: 25000, contracts_expiring_2027: 1 });"}
                                        ),
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            }
        return {
            "choices": [{"message": {"content": "Total calculado: USD 25000 (1 contrato vence en 2027)."}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 45},
        }

    audit = AuditLogger()
    cfg = ResolvedLLMConfig(
        provider="ollama",
        api_key="ollama-local",
        model="qwen2.5:3b",
        base_url="http://127.0.0.1:11434/v1",
        allow_local=True,
        source="database",
    )
    graph = ResearchAgentGraph(
        registry=ToolRegistry(),
        model_client=build_agent_model_client(cfg, transport=fake_llm),
        repo=InMemoryRunsRepository(),
        checkpointer=InMemoryCheckpointer(),
        quota_service=TenantQuotaService(),
        audit_logger=audit,
        sandbox_client=SandboxHttpClient(transport=fake_sandbox_transport),
    )

    run = graph.start_run(
        user={"user_id": "u-1", "active_tenant_id": "t-1", "raw_token": "secret.jwt.never.sent"},
        goal="Calcula suma de montos y vencimientos",
        enable_code_mode=True,
        idempotency_key="cm-1",
    )
    assert run["status"] == "SUCCEEDED"
    assert len(run["code_executions"]) == 1
    assert run["code_executions"][0]["output"]["total_amount"] == 25000
    assert "secret.jwt.never.sent" not in json.dumps(sandbox_payloads[0])
    assert any(ev["event_type"] == "agent.code_mode.executed" for ev in audit.events)
