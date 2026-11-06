from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.transfer_repository_pg import TransferRepositoryPg
from app.shared.errors import NotFoundError


def wait_for_lock(engine, pid, future):
    deadline = monotonic() + 5
    tick = Event()
    with engine.connect() as observer:
        while monotonic() < deadline:
            if observer.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}) == "Lock":
                return
            if future.done():
                future.result()
                pytest.fail("Operation completed without waiting for the reference lock")
            observer.rollback()
            tick.wait(0.02)
    pytest.fail("Expected PostgreSQL lock wait was not observed")


@pytest.mark.parametrize("operation", ["create", "patch"])
def test_reference_first_blocks_delete_then_preserves_history(engine, committed_records, operation):
    document, transfer, owner = committed_records
    reference_ready, release = Event(), Event()
    delete_pid = Queue()

    def write():
        with Session(engine) as session:
            def pause_before_commit(current):
                reference_ready.set()
                assert release.wait(10), "Reference transaction was not released"
            event.listen(session, "before_commit", pause_before_commit, once=True)
            repository = TransferRepositoryPg(session, {"user_id": owner})
            if operation == "create":
                row = repository.create({"filename": "synthetic.txt", "direction": "UPLOAD", "status": "PENDING", "document_id": document})
            else:
                row = repository.update(transfer, {"document_id": document})
            return row.transfer_id

    def delete():
        with engine.begin() as connection:
            delete_pid.put(connection.scalar(text("SELECT pg_backend_pid()")))
            connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        writer = pool.submit(write)
        assert reference_ready.wait(5)
        deleter = pool.submit(delete)
        wait_for_lock(engine, delete_pid.get(timeout=5), deleter)
        release.set()
        identifier = writer.result(timeout=5)
        deleter.result(timeout=5)
        with engine.connect() as connection:
            row = connection.execute(text("SELECT document_id, filename FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}).one()
            assert row.document_id is None and row.filename == "synthetic.txt"
    finally:
        release.set()
        pool.shutdown(wait=True)


@pytest.mark.parametrize("operation", ["create", "patch"])
def test_delete_first_rejects_reference_without_fk_error_and_recovers(engine, committed_records, operation):
    document, transfer, owner = committed_records
    write_pid = Queue()

    def write():
        with Session(engine) as session:
            write_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            repository = TransferRepositoryPg(session, {"user_id": owner})
            with pytest.raises(NotFoundError, match="Document not found"):
                if operation == "create":
                    repository.create({"filename": "synthetic.txt", "direction": "UPLOAD", "status": "PENDING", "document_id": document})
                else:
                    repository.update(transfer, {"document_id": document, "progress": 50})
            assert session.scalar(text("SELECT 1")) == 1

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document})
                writer = pool.submit(write)
                wait_for_lock(engine, write_pid.get(timeout=5), writer)
                transaction.commit()
            finally:
                if transaction.is_active:
                    transaction.rollback()
        writer.result(timeout=5)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 1
            assert connection.execute(text("SELECT document_id, progress FROM transfer_events WHERE transfer_id=:id"), {"id": transfer}).one() == (None, 0)
    finally:
        pool.shutdown(wait=True)
