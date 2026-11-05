import asyncio
import logging

from app.application.documents.use_cases.cleanup_document_deletion import CleanupDocumentDeletion
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


logger = logging.getLogger(__name__)


def cleanup_pending_batch(database: Database, path_resolver: LocalDocumentPathResolver) -> None:
    with database.session() as session:
        repository = DocumentAccessRepositoryPg(session)
        cleanup = CleanupDocumentDeletion(repository, path_resolver)
        for document_id in repository.pending_deletions():
            try:
                cleanup.execute(document_id, skip_locked=True)
            except Exception as exc:
                repository.release_deletion()
                logger.warning("Document deletion cleanup failed (%s).", type(exc).__name__)


async def deletion_cleanup_loop(database: Database, path_resolver: LocalDocumentPathResolver, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(cleanup_pending_batch, database, path_resolver)
        except Exception as exc:
            logger.warning("Document deletion queue is unavailable (%s).", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except TimeoutError:
            pass
