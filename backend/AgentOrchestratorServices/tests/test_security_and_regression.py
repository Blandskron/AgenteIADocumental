from __future__ import annotations

from app.application.tools.registry import redact_secrets
from app.infrastructure.database.audit_logger import sanitize_audit_metadata
from app.infrastructure.database.runs_repository import InMemoryRunsRepository


def test_audit_metadata_never_leaks_tokens_or_private_chunk_text() -> None:
    sanitized = sanitize_audit_metadata(
        {
            "raw_token": "eyJhbGciOiJSUzI1NiJ9.secret",
            "api_key": "gsk_live_secret_999",
            "chunk_content": "Datos personales confidenciales",
            "note": "Error con Bearer token.abc.123 y secrets1.v1.xyz",
            "steps_used": 3,
        }
    )
    assert "raw_token" not in sanitized
    assert "api_key" not in sanitized
    assert "chunk_content" not in sanitized
    assert "token.abc.123" not in sanitized["note"]
    assert "secrets1.v1.xyz" not in sanitized["note"]
    assert sanitized["steps_used"] == 3
    assert "gsk_live_secret_999" not in redact_secrets("gsk_live_secret_999")


def test_runs_repository_enforces_strict_multi_tenant_and_user_isolation() -> None:
    repo = InMemoryRunsRepository()
    r1 = repo.create_run(
        tenant_id="tenant-1",
        owner_user_id="user-1",
        idempotency_key="k1",
        mode="agent",
        goal="Tenant 1 goal",
        document_ids=["doc-1"],
    )
    r2 = repo.create_run(
        tenant_id="tenant-2",
        owner_user_id="user-2",
        idempotency_key="k1",  # Same key in different tenant is allowed & isolated
        mode="agent",
        goal="Tenant 2 goal",
        document_ids=["doc-2"],
    )
    assert r1["run_id"] != r2["run_id"]
    assert len(repo.list_runs(tenant_id="tenant-1", owner_user_id="user-1")) == 1
    assert repo.get_run(r2["run_id"], tenant_id="tenant-1", owner_user_id="user-1") is None
    assert repo.request_cancel(r2["run_id"], tenant_id="tenant-1", owner_user_id="user-1") is None
