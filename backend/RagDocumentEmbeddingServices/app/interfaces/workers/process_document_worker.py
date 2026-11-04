import logging

from sqlalchemy.orm import Session

from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.config.settings import Settings
from app.interfaces.api.v1.dependencies import build_ingest_existing_document

logger = logging.getLogger(__name__)


def build_document_worker(session: Session, settings: Settings) -> IngestExistingDocument:
    return build_ingest_existing_document(session, settings)


def process_document(document_id: str, session: Session, settings: Settings) -> None:
    logger.info("Worker received document %s", document_id)
    build_document_worker(session, settings).execute(document_id)
