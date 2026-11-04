from app.application.documents.ports import DocumentSearchRepository
from app.domain.documents import ChatDocumentSelection, InvalidDocumentSelectionError


class BuildChatContext:
    def __init__(self, repository: DocumentSearchRepository) -> None:
        self._repository = repository

    def execute(self, document_ids: list[str], session_id: str | None = None) -> ChatDocumentSelection:
        unique_ids = list(dict.fromkeys(document_ids))
        if not unique_ids:
            raise InvalidDocumentSelectionError("At least one document_id is required.")

        documents = self._repository.get_many_by_ids(unique_ids)
        found_ids = {document.document_id for document in documents}
        missing_ids = [document_id for document_id in unique_ids if document_id not in found_ids]
        if missing_ids:
            raise InvalidDocumentSelectionError(f"Documents not found: {', '.join(missing_ids)}")

        unavailable = [document.filename for document in documents if document.status != "PROCESSED"]
        if unavailable:
            raise InvalidDocumentSelectionError(
                "Only processed documents can be sent to chat: " + ", ".join(unavailable)
            )

        filenames = ", ".join(document.filename for document in documents)
        return ChatDocumentSelection(
            session_id=session_id,
            documents=documents,
            suggested_prompt=f"Analiza los documentos seleccionados: {filenames}",
        )
