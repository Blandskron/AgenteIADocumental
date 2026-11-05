from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from os import environ
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.application.documents.use_cases.cleanup_document_deletion import CleanupDocumentDeletion
from app.application.documents.use_cases.delete_document import DeleteDocument
from app.config.settings import get_settings
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


@pytest.fixture
def committed_document(tmp_path):
    engine = create_engine(environ["ACCESS_TEST_DATABASE_URL"])
    runtime_engine = create_engine(get_settings().database_url)
    document_id = uuid4().hex
    path = tmp_path / "committed.txt"
    path.write_text("Synthetic committed document", encoding="utf-8")
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO documents (document_id, owner_user_id, filename, storage_path, mime_type)
                VALUES (:id, '42', 'committed.txt', :path, 'text/plain')
            """), {"id": document_id, "path": str(path)})
        yield runtime_engine, document_id, path, engine
    finally:
        with engine.begin() as connection:
            for table, key in (("documents", "document_id"), ("document_deletions", "document_id"), ("audit_logs", "resource_id")):
                connection.execute(text(f"DELETE FROM {table} WHERE {key} = :id"), {"id": document_id})
        engine.dispose()
        runtime_engine.dispose()


def test_fresh_session_recovers_cleanup_after_committed_removal(committed_document):
    engine, document_id, path, admin_engine = committed_document
    with Session(engine) as session:
        repository = DocumentAccessRepositoryPg(session, {"user_id": 42})
        assert repository.prepare_deletion(document_id) is not None
    assert path.exists()
    with admin_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id = :id"), {"id": document_id}) == 0
        assert connection.scalar(text("SELECT count(*) FROM document_deletions WHERE document_id = :id"), {"id": document_id}) == 1
    with Session(engine) as session:
        cleanup = CleanupDocumentDeletion(
            DocumentAccessRepositoryPg(session), LocalDocumentPathResolver(str(path.parent)),
        )
        assert cleanup.execute(document_id).file_deleted is True
    assert not path.exists()


def test_two_concurrent_deletes_share_one_cleanup(committed_document):
    engine, document_id, path, admin_engine = committed_document
    barrier = Barrier(2)

    def remove_document():
        with Session(engine) as session:
            use_case = DeleteDocument(
                DocumentAccessRepositoryPg(session, {"user_id": 42}),
                LocalDocumentPathResolver(str(path.parent)),
            )
            barrier.wait(timeout=10)
            return use_case.execute(document_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(remove_document) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert all(result.deleted and result.file_deleted for result in results)
    assert not path.exists()
    with admin_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_deletions WHERE document_id = :id"), {"id": document_id}) == 1
        assert connection.scalar(text("SELECT count(*) FROM audit_logs WHERE resource_id = :id AND action = 'DOCUMENT_DELETED'"), {
            "id": document_id,
        }) == 1


def test_cleanup_worker_skips_locked_job(committed_document):
    engine, document_id, path, _ = committed_document
    with Session(engine) as session:
        DocumentAccessRepositoryPg(session, {"user_id": 42}).prepare_deletion(document_id)
    with Session(engine) as holder:
        locked_repository = DocumentAccessRepositoryPg(holder)
        assert locked_repository.claim_deletion(document_id) is not None
        with Session(engine) as contender:
            cleanup = CleanupDocumentDeletion(
                DocumentAccessRepositoryPg(contender), LocalDocumentPathResolver(str(path.parent)),
            )
            assert cleanup.execute(document_id, skip_locked=True) is None
        assert path.exists()
        locked_repository.release_deletion()
    with Session(engine) as session:
        cleanup = CleanupDocumentDeletion(
            DocumentAccessRepositoryPg(session), LocalDocumentPathResolver(str(path.parent)),
        )
        assert cleanup.execute(document_id).file_deleted is True
