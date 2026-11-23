import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.config.settings import Settings
from app.interfaces.api.v1.dependencies import build_ingest_existing_document

logger = logging.getLogger(__name__)


def build_document_worker(session: Session, settings: Settings) -> IngestExistingDocument:
    return build_ingest_existing_document(session, settings)


def claim_next_pending_document(session: Session) -> str | None:
    """Atomically claims one PENDING document using PostgreSQL FOR UPDATE SKIP LOCKED (EVO-009)."""
    row = session.execute(
        text(
            """
            WITH next_doc AS (
                SELECT document_id
                FROM public.documents
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE public.documents d
            SET status = 'PROCESSING',
                updated_at = NOW()
            FROM next_doc
            WHERE d.document_id = next_doc.document_id
            RETURNING d.document_id
            """
        )
    ).mappings().first()
    session.commit()
    return str(row["document_id"]) if row is not None else None


def process_document(document_id: str, session: Session, settings: Settings) -> None:
    logger.info("Worker received document %s", document_id)
    build_document_worker(session, settings).execute(document_id)


def process_next_pending_document(session: Session, settings: Settings) -> str | None:
    """Claims and processes the next queued PENDING document; returns document_id or None."""
    document_id = claim_next_pending_document(session)
    if document_id is None:
        return None
    process_document(document_id, session, settings)
    return document_id
