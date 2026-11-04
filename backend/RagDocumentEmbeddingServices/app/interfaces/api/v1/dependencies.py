from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.documents.ports.document_reader import DocumentReader
from app.application.documents.use_cases.extract_document_content import ExtractDocumentContent
from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.application.documents.use_cases.upload_document import UploadDocument
from app.application.embeddings.use_cases.create_document_embeddings import CreateDocumentEmbeddings
from app.config.database import get_session
from app.config.settings import Settings, get_settings
from app.infrastructure.ai.embedding_provider_local import MODEL_NAME, LocalEmbeddingProvider
from app.infrastructure.database.repositories.document_reader_pg import DocumentReaderPg
from app.infrastructure.database.repositories.document_writer_pg import DocumentWriterPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.infrastructure.extractors.docx_extractor import DocxExtractor
from app.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from app.infrastructure.extractors.pdf_extractor import PdfExtractor
from app.infrastructure.extractors.plain_text_extractor import PlainTextExtractor
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.infrastructure.storage.document_storage import LocalDocumentStorage


def get_document_reader(session: Session = Depends(get_session)) -> DocumentReader:
    return DocumentReaderPg(session)


def build_embedding_provider() -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider()


def get_ingest_existing_document(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> IngestExistingDocument:
    return build_ingest_existing_document(session, settings)


def build_ingest_existing_document(session: Session, settings: Settings) -> IngestExistingDocument:
    document_reader = DocumentReaderPg(session)
    document_writer = DocumentWriterPg(session)
    vector_repository = VectorRepositoryPgVector(session)
    embedding_provider = build_embedding_provider()
    extractors = [PdfExtractor(), DocxExtractor(), PlainTextExtractor(), ImageOcrExtractor()]

    return IngestExistingDocument(
        document_reader=document_reader,
        document_writer=document_writer,
        path_resolver=LocalDocumentPathResolver(settings.document_storage_base_path),
        content_extractor=ExtractDocumentContent(extractors),
        embedding_creator=CreateDocumentEmbeddings(
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embedding_model=MODEL_NAME,
        ),
    )


def get_upload_document(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadDocument:
    return UploadDocument(
        document_writer=DocumentWriterPg(session),
        storage=LocalDocumentStorage(settings.document_storage_base_path),
        ingestion=build_ingest_existing_document(session, settings),
    )
