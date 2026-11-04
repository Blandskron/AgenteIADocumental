from app.application.documents.ports import DocumentReader, DocumentWriter
from app.application.documents.use_cases.extract_document_content import ExtractDocumentContent
from app.application.embeddings.use_cases.create_document_embeddings import CreateDocumentEmbeddings
from app.domain.documents import DocumentNotFoundError


class IngestExistingDocument:
    def __init__(
        self,
        document_reader: DocumentReader,
        document_writer: DocumentWriter,
        path_resolver,
        content_extractor: ExtractDocumentContent,
        embedding_creator: CreateDocumentEmbeddings,
    ) -> None:
        self._document_reader = document_reader
        self._document_writer = document_writer
        self._path_resolver = path_resolver
        self._content_extractor = content_extractor
        self._embedding_creator = embedding_creator

    def execute(self, document_id: str) -> None:
        document = self._document_reader.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")

        self._document_writer.mark_as_processing(document_id)
        try:
            file_path = self._path_resolver.resolve(document.storage_path)
            text = self._content_extractor.execute(file_path, document.mime_type)
            metadata = {
                **(document.metadata or {}),
                "filename": document.filename,
                "mime_type": document.mime_type,
                "storage_path": document.storage_path,
            }
            self._embedding_creator.execute(document_id=document_id, text=text, metadata=metadata)
            self._document_writer.mark_as_processed(document_id)
        except Exception as exc:
            self._document_writer.mark_as_failed(document_id, str(exc))
            raise
