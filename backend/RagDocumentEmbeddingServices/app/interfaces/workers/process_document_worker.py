import logging

from sqlalchemy.orm import Session

from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.config.settings import Settings
from app.infrastructure.ai.embedding_provider_local import MODEL_NAME
from app.interfaces.api.v1.dependencies import build_embedding_provider
from app.infrastructure.database.repositories.document_reader_pg import DocumentReaderPg
from app.infrastructure.database.repositories.document_writer_pg import DocumentWriterPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.infrastructure.extractors.docx_extractor import DocxExtractor
from app.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from app.infrastructure.extractors.pdf_extractor import PdfExtractor
from app.infrastructure.extractors.plain_text_extractor import PlainTextExtractor
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.application.documents.use_cases.extract_document_content import ExtractDocumentContent
from app.application.embeddings.use_cases.create_document_embeddings import CreateDocumentEmbeddings

logger = logging.getLogger(__name__)


def build_document_worker(session: Session, settings: Settings) -> IngestExistingDocument:
    embedding_provider = build_embedding_provider()
    vector_repository = VectorRepositoryPgVector(session)
    return IngestExistingDocument(
        document_reader=DocumentReaderPg(session),
        document_writer=DocumentWriterPg(session),
        path_resolver=LocalDocumentPathResolver(settings.document_storage_base_path),
        content_extractor=ExtractDocumentContent(
            [PdfExtractor(), DocxExtractor(), PlainTextExtractor(), ImageOcrExtractor()]
        ),
        embedding_creator=CreateDocumentEmbeddings(
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embedding_model=MODEL_NAME,
        ),
    )


def process_document(document_id: str, session: Session, settings: Settings) -> None:
    logger.info("Worker received document %s", document_id)
    build_document_worker(session, settings).execute(document_id)
