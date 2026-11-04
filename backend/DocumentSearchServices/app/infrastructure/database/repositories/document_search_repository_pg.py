from sqlalchemy import exists, false, func, or_
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, user_groups, user_id
from app.domain.documents import DocumentChunk, DocumentSearchResult, DocumentSummary
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentEmbeddingModel, DocumentModel


class DocumentSearchRepositoryPg:
    def __init__(self, session: Session, current_user: dict | None = None) -> None:
        self._session = session
        self._current_user = current_user or {}

    def search(
        self,
        query: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_desc",
    ) -> DocumentSearchResult:
        statement = self._accessible_documents_query()
        statement = self._apply_filters(statement, query, status, mime_type, source)
        total = statement.count()
        documents = statement.order_by(self._sort_clause(sort)).offset(offset).limit(limit).all()

        return DocumentSearchResult(
            items=[self._to_summary(document, query=query) for document in documents],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_by_id(self, document_id: str) -> DocumentSummary | None:
        document = self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()
        if document is None:
            return None
        return self._to_summary(document)

    def get_many_by_ids(self, document_ids: list[str]) -> list[DocumentSummary]:
        if not document_ids:
            return []
        documents = self._accessible_documents_query().filter(DocumentModel.document_id.in_(document_ids)).all()
        by_id = {str(document.document_id): self._to_summary(document) for document in documents}
        return [by_id[document_id] for document_id in document_ids if document_id in by_id]

    def get_chunks(
        self,
        document_id: str,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        statement = (
            self._session.query(DocumentEmbeddingModel)
            .join(DocumentModel, DocumentEmbeddingModel.document_id == DocumentModel.document_id)
            .filter(DocumentEmbeddingModel.document_id == document_id)
        )
        statement = self._apply_access_filter(statement)
        if query:
            statement = statement.filter(DocumentEmbeddingModel.chunk_content.ilike(f"%{query}%"))

        total = statement.count()
        rows = statement.order_by(DocumentEmbeddingModel.chunk_index.asc()).offset(offset).limit(limit).all()
        return [
            DocumentChunk(
                chunk_id=str(row.chunk_id),
                document_id=str(row.document_id),
                chunk_index=row.chunk_index,
                content=row.chunk_content,
                metadata=row.metadata_ or {},
                created_at=row.created_at,
            )
            for row in rows
        ], total

    def _apply_filters(self, statement, query, status, mime_type, source):
        if status:
            statement = statement.filter(DocumentModel.status == status)
        if mime_type:
            statement = statement.filter(DocumentModel.mime_type == mime_type)
        if source:
            statement = statement.filter(DocumentModel.metadata_.op("->>")("source") == source)
        if query:
            like_query = f"%{query}%"
            matching_chunk_exists = exists().where(
                DocumentEmbeddingModel.document_id == DocumentModel.document_id,
                DocumentEmbeddingModel.chunk_content.ilike(like_query),
            )
            statement = statement.filter(or_(DocumentModel.filename.ilike(like_query), matching_chunk_exists))
        return statement

    def _accessible_documents_query(self):
        return self._apply_access_filter(self._session.query(DocumentModel))

    def _apply_access_filter(self, statement):
        if is_superadmin_user(self._current_user):
            return statement

        clauses = []
        current_user_id = user_id(self._current_user)
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(DocumentModel.tenant_id.in_(admin_tenant_ids))
            clauses.append(DocumentModel.metadata_.op("->>")("tenant_id").in_(admin_tenant_ids))
        if current_user_id:
            assigned_document_ids = (
                self._session.query(DocumentAssignmentModel.document_id)
                .filter(DocumentAssignmentModel.assigned_to_user_id == current_user_id)
                .subquery()
            )
            managed_document_ids = (
                self._session.query(DocumentAssignmentModel.document_id)
                .filter(DocumentAssignmentModel.assigned_by_user_id == current_user_id)
                .subquery()
            )
            clauses.append(DocumentModel.owner_user_id == current_user_id)
            clauses.append(DocumentModel.metadata_.op("->>")("owner_user_id") == current_user_id)
            clauses.append(DocumentModel.document_id.in_(assigned_document_ids))
            clauses.append(DocumentModel.document_id.in_(managed_document_ids))
        for group in user_groups(self._current_user):
            clauses.append(DocumentModel.metadata_.contains({"owner_groups": [group]}))
        return statement.filter(or_(*clauses) if clauses else false())

    def _sort_clause(self, sort: str):
        options = {
            "created_asc": DocumentModel.created_at.asc(),
            "created_desc": DocumentModel.created_at.desc(),
            "filename_asc": DocumentModel.filename.asc(),
            "filename_desc": DocumentModel.filename.desc(),
            "updated_desc": DocumentModel.updated_at.desc(),
        }
        return options.get(sort, DocumentModel.created_at.desc())

    def _to_summary(self, document: DocumentModel, query: str | None = None) -> DocumentSummary:
        return DocumentSummary(
            document_id=str(document.document_id),
            filename=document.filename,
            mime_type=document.mime_type,
            status=document.status,
            metadata=document.metadata_ or {},
            chunk_count=self._chunk_count(str(document.document_id)),
            processing_error=document.processing_error,
            processed_at=document.processed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
            snippet=self._snippet(str(document.document_id), query),
        )

    def _chunk_count(self, document_id: str) -> int:
        return int(
            self._session.query(func.count(DocumentEmbeddingModel.chunk_id))
            .filter(DocumentEmbeddingModel.document_id == document_id)
            .scalar()
            or 0
        )

    def _snippet(self, document_id: str, query: str | None) -> str | None:
        if not query:
            return None
        row = (
            self._session.query(DocumentEmbeddingModel.chunk_content)
            .filter(
                DocumentEmbeddingModel.document_id == document_id,
                DocumentEmbeddingModel.chunk_content.ilike(f"%{query}%"),
            )
            .order_by(DocumentEmbeddingModel.chunk_index.asc())
            .first()
        )
        if row is None:
            return None
        content = row.chunk_content.strip()
        return content[:360]
