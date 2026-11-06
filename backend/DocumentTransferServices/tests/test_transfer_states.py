from uuid import uuid4

import jwt
import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.main import app


STATES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


@pytest.fixture
def records(configured_client, signing_key, engine):
    client, _ = configured_client
    owner = int(uuid4().hex[:12], 16)
    headers = {"Authorization": "Bearer " + jwt.encode({"user_id": owner, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                app.dependency_overrides[get_session] = lambda: session
                yield client, session, headers, owner, engine
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0


def create(client, headers, status="RUNNING", progress=40):
    return client.post("/api/v1/transfers", headers=headers,
                       json={"filename": "synthetic.txt", "direction": "UPLOAD", "status": status, "progress": progress})


@pytest.mark.parametrize("current", STATES)
@pytest.mark.parametrize("target", STATES)
def test_state_transition_matrix_is_private_and_atomic(records, current, target):
    client, session, headers, _, _ = records
    initial = 100 if current == "COMPLETED" else 40
    row = create(client, headers, current, initial)
    assert row.status_code == 200
    identifier = row.json()["transfer_id"]
    progress = 100 if target == "COMPLETED" else initial
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": target, "progress": progress})
    allowed = (current not in TERMINAL or target == current) and not (current == "RUNNING" and target == "PENDING")
    assert response.status_code == (200 if allowed else 409)
    stored = session.execute(text("SELECT status, progress FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}).one()
    assert stored == ((target, progress) if allowed else (current, initial))
    assert session.scalar(text("SELECT 1")) == 1


@pytest.mark.parametrize("status", STATES)
def test_progress_never_regresses_and_terminal_progress_is_frozen(records, status):
    client, session, headers, _, _ = records
    progress = 100 if status == "COMPLETED" else 40
    identifier = create(client, headers, status, progress).json()["transfer_id"]
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"progress": progress - 1}).status_code == 409
    higher = 50 if status != "COMPLETED" else 100
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"progress": higher})
    assert response.status_code == (409 if status in ("FAILED", "CANCELLED") else 200)
    # Metadata corrections do not reopen or rewrite an existing terminal state.
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"metadata": {"note": "synthetic"}}).status_code == 200
    assert session.scalar(text("SELECT status FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}) == status


def test_completion_requires_100_and_failure_keeps_last_stage(records):
    client, session, headers, owner, _ = records
    assert create(client, headers, "COMPLETED", 1).status_code == 400
    assert session.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0
    identifier = create(client, headers, "RUNNING", 65).json()["transfer_id"]
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": "COMPLETED"}).status_code == 409
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": "FAILED", "progress": 15}).status_code == 409
    failed = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": "FAILED", "metadata": {"error": "synthetic"}})
    assert failed.status_code == 200 and failed.json()["progress"] == 65
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"status": "RUNNING"}).status_code == 409


@pytest.mark.parametrize("status", STATES)
def test_identical_patch_retry_issues_no_update(records, status):
    client, _, headers, _, engine = records
    progress = 100 if status == "COMPLETED" else 40
    identifier = create(client, headers, status, progress).json()["transfer_id"]
    payload = {"status": status, "progress": progress, "metadata": {"retry": "synthetic"}}
    first = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json=payload)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE"):
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        second = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json=payload)
        assert second.status_code == 200
        assert first.json() == second.json()
        assert not statements
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_clear_is_bounded_preserves_active_foreign_and_counts_actual_deletes(records):
    client, session, headers, owner, engine = records
    foreign = str(owner + 1)
    session.execute(text("""
        INSERT INTO transfer_events (owner_user_id, filename, direction, status, progress)
        SELECT :owner, 'synthetic.txt', 'UPLOAD', 'COMPLETED', 100 FROM generate_series(1,1001)
    """), {"owner": str(owner)})
    session.execute(text("""
        INSERT INTO transfer_events (owner_user_id, filename, direction, status, progress)
        VALUES (:owner, 'synthetic.txt', 'UPLOAD', 'RUNNING', 65), (:owner, 'synthetic.txt', 'UPLOAD', 'PENDING', 0),
               (:foreign, 'synthetic.txt', 'UPLOAD', 'COMPLETED', 100)
    """), {"owner": str(owner), "foreign": foreign})
    session.commit()
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 1000}
        # No ORM SELECT/materialization of history: lock statement and a DELETE with limited subquery.
        assert len(statements) <= 4
        assert not any(statement.lstrip().startswith("SELECT transfer_events") for statement in statements)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 1}
    assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 0}
    assert session.scalars(text("SELECT status FROM transfer_events WHERE owner_user_id=:owner ORDER BY status"), {"owner": str(owner)}).all() == ["PENDING", "RUNNING"]
    assert session.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": foreign}) == 1
