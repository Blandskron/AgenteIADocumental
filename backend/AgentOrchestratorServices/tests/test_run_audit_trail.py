from __future__ import annotations

from app.infrastructure.database.audit_logger import AuditLogger


def test_audit_logger_lists_run_events_strictly_scoped_by_tenant() -> None:
    logger = AuditLogger()
    logger.record(
        event_type="agent.run.started",
        tenant_id="t1",
        actor_user_id="u1",
        run_id="run_a",
        metadata={"provider": "ollama", "raw_token": "secret.should.drop"},
    )
    logger.record(
        event_type="agent.run.completed",
        tenant_id="t1",
        actor_user_id="u1",
        run_id="run_a",
        metadata={"steps_used": 2},
    )
    logger.record(
        event_type="agent.run.started",
        tenant_id="t2",
        actor_user_id="u2",
        run_id="run_a",
        metadata={"provider": "groq"},
    )

    t1_events = logger.list_for_run(run_id="run_a", tenant_id="t1")
    assert len(t1_events) == 2
    assert all("raw_token" not in ev["metadata"] for ev in t1_events)
    assert len(logger.list_for_run(run_id="run_a", tenant_id="t2")) == 1
    assert logger.list_for_run(run_id="run_a", tenant_id="t3") == []
