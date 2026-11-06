from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.transfer_repository_pg import TransferRepositoryPg
from app.shared.errors import ConflictError
from test_reference_concurrency import wait_for_lock


@pytest.mark.parametrize("scenario", ["progress", "terminal", "patch_clear", "clear_patch", "clear_clear", "create_clear", "rollback_clear"])
def test_same_owner_writes_serialize_with_effective_results(engine, committed_records, scenario):
    document, transfer, owner = committed_records
    paused, release = Event(), Event()
    second_pid = Queue()
    if scenario in ("clear_patch", "clear_clear"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE transfer_events SET status='COMPLETED', progress=100 WHERE transfer_id=:id"), {"id": transfer})

    def first():
        with Session(engine) as session:
            def before_commit(current):
                paused.set()
                assert release.wait(10)
                if scenario == "rollback_clear":
                    raise RuntimeError("Synthetic transaction interruption")
            event.listen(session, "before_commit", before_commit, once=True)
            repository = TransferRepositoryPg(session, {"user_id": owner})
            if scenario in ("clear_patch", "clear_clear"):
                return repository.clear_history()
            if scenario == "create_clear":
                return repository.create({"filename": "synthetic.txt", "direction": "UPLOAD", "status": "COMPLETED", "progress": 100})
            payload = {"progress": 65} if scenario == "progress" else {"status": "COMPLETED", "progress": 100}
            if scenario == "rollback_clear":
                with pytest.raises(RuntimeError, match="Synthetic transaction interruption"):
                    repository.update(transfer, payload)
                return "rolled_back"
            return repository.update(transfer, payload)

    def second():
        with Session(engine) as session:
            second_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            repository = TransferRepositoryPg(session, {"user_id": owner})
            if scenario in ("patch_clear", "clear_clear", "create_clear", "rollback_clear"):
                return repository.clear_history()
            if scenario == "clear_patch":
                return repository.update(transfer, {"metadata_": {"late": "synthetic"}})
            with pytest.raises(ConflictError):
                repository.update(transfer, {"progress": 15} if scenario == "progress" else {"status": "FAILED"})
            assert session.scalar(text("SELECT 1")) == 1
            return "conflict"

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        one = pool.submit(first)
        assert paused.wait(5)
        two = pool.submit(second)
        wait_for_lock(engine, second_pid.get(timeout=5), two)
        release.set()
        initial, following = one.result(timeout=5), two.result(timeout=5)
        if scenario == "rollback_clear":
            assert initial == "rolled_back" and following == 0
            with engine.connect() as connection:
                assert connection.execute(text("SELECT status, progress FROM transfer_events WHERE transfer_id=:id"), {"id": transfer}).one() == ("PENDING", 0)
        elif scenario == "clear_patch":
            assert initial == 1 and following is None
        elif scenario == "clear_clear":
            assert initial == 1 and following == 0
        elif scenario in ("patch_clear", "create_clear"):
            # The first response remains usable even after cleanup has removed its row.
            assert initial.status == "COMPLETED" and initial.progress == 100
            assert following == 1
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE transfer_id=:id"), {"id": initial.transfer_id}) == 0
        else:
            assert following == "conflict"
            with engine.connect() as connection:
                row = connection.execute(text("SELECT status, progress FROM transfer_events WHERE transfer_id=:id"), {"id": transfer}).one()
                assert row == (("PENDING", 65) if scenario == "progress" else ("COMPLETED", 100))
    finally:
        release.set()
        pool.shutdown(wait=True)


@pytest.mark.parametrize("operation", ["clear", "patch"])
def test_document_delete_and_history_mutation_use_safe_lock_order(engine, committed_records, operation):
    document, transfer, owner = committed_records
    with engine.begin() as connection:
        connection.execute(text("UPDATE transfer_events SET document_id=:document, status='COMPLETED', progress=100 WHERE transfer_id=:id"),
                           {"document": document, "id": transfer})
    waiting_pid = Queue()

    def mutate():
        with Session(engine) as session:
            waiting_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            repository = TransferRepositoryPg(session, {"user_id": owner})
            if operation == "clear":
                return repository.clear_history()
            return repository.update(transfer, {"metadata_": {"synthetic": True}})

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})
                pending = pool.submit(mutate)
                wait_for_lock(engine, waiting_pid.get(timeout=5), pending)
                transaction.commit()
            finally:
                if transaction.is_active:
                    transaction.rollback()
        result = pending.result(timeout=5)
        if operation == "clear":
            assert result == 1
        else:
            assert result.document_id is None and result.metadata_ == {"synthetic": True}
    finally:
        pool.shutdown(wait=True)


def test_other_owners_are_independent(engine, committed_records):
    _, transfer, owner = committed_records
    pool = ThreadPoolExecutor(max_workers=1)

    def other_owner():
        with Session(engine) as session:
            return TransferRepositoryPg(session, {"user_id": owner + 1}).create({
                "filename": "synthetic.txt", "direction": "UPLOAD", "status": "PENDING"})

    try:
        with Session(engine) as session:
            repository = TransferRepositoryPg(session, {"user_id": owner})
            repository._lock_owner()
            row = pool.submit(other_owner).result(timeout=5)
            session.rollback()
        assert row.owner_user_id == str(owner + 1)
    finally:
        pool.shutdown(wait=True)
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner + 1)})


@pytest.mark.parametrize("operation", ["clear", "patch"])
def test_history_mutation_first_allows_document_delete_to_finish(engine, committed_records, operation):
    document, transfer, owner = committed_records
    with engine.begin() as connection:
        connection.execute(text("UPDATE transfer_events SET document_id=:document, status='COMPLETED', progress=100 WHERE transfer_id=:id"),
                           {"document": document, "id": transfer})
    paused, release, deleting_pid = Event(), Event(), Queue()

    def mutate():
        with Session(engine) as session:
            def before_commit(current):
                paused.set()
                assert release.wait(10)
            event.listen(session, "before_commit", before_commit, once=True)
            repository = TransferRepositoryPg(session, {"user_id": owner})
            return repository.clear_history() if operation == "clear" else repository.update(transfer, {"metadata_": {"synthetic": True}})

    def delete():
        with engine.begin() as connection:
            deleting_pid.put(connection.scalar(text("SELECT pg_backend_pid()")))
            connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        mutation = pool.submit(mutate)
        assert paused.wait(5)
        deletion = pool.submit(delete)
        wait_for_lock(engine, deleting_pid.get(timeout=5), deletion)
        release.set()
        result = mutation.result(timeout=5)
        deletion.result(timeout=5)
        assert result == 1 if operation == "clear" else result.metadata_ == {"synthetic": True}
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": document}) == 0
            row = connection.execute(text("SELECT document_id FROM transfer_events WHERE transfer_id=:id"), {"id": transfer}).one_or_none()
            assert row is None if operation == "clear" else row == (None,)
    finally:
        release.set()
        pool.shutdown(wait=True)


def test_real_commit_failure_rolls_back_then_session_recovers(engine, committed_records):
    _, transfer, owner = committed_records
    with Session(engine) as session:
        def fail(current):
            raise RuntimeError("Synthetic commit interruption")
        event.listen(session, "before_commit", fail, once=True)
        repository = TransferRepositoryPg(session, {"user_id": owner})
        with pytest.raises(RuntimeError, match="Synthetic commit interruption"):
            repository.update(transfer, {"progress": 65})
        assert session.scalar(text("SELECT progress FROM transfer_events WHERE transfer_id=:id"), {"id": transfer}) == 0
        assert repository.update(transfer, {"progress": 65}).progress == 65
