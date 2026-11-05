from sqlalchemy import func, null, or_, select
from sqlalchemy.orm import Session, defer

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.domain.documents import DocumentChunk, DocumentSearchResult, DocumentSummary
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentEmbeddingModel, DocumentModel


class DocumentSearchRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._current_user = current_user

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
        documents = self._with_summaries(statement, query).order_by(
            self._sort_clause(sort), DocumentModel.document_id.asc(),
        ).offset(offset).limit(limit).all()

        return DocumentSearchResult(
            items=[self._to_summary(*row) for row in documents],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_by_id(self, document_id: str) -> DocumentSummary | None:
        statement = self._accessible_documents_query().filter(DocumentModel.document_id == document_id)
        row = self._with_summaries(statement).first()
        return self._to_summary(*row) if row is not None else None

    def get_many_by_ids(self, document_ids: list[str]) -> list[DocumentSummary]:
        if not document_ids:
            return []
        statement = self._accessible_documents_query().filter(DocumentModel.document_id.in_(document_ids))
        summaries = [self._to_summary(*row) for row in self._with_summaries(statement).all()]
        by_id = {summary.document_id: summary for summary in summaries}
        return [by_id[document_id] for document_id in document_ids if document_id in by_id]

    def get_chunks(
        self,
        document_id: str,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        statement = (
            self._session.query(
                DocumentEmbeddingModel.chunk_id,
                DocumentEmbeddingModel.document_id,
                DocumentEmbeddingModel.chunk_index,
                DocumentEmbeddingModel.chunk_content,
                DocumentEmbeddingModel.created_at,
            )
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
            matching_chunk_exists = select(1).where(
                DocumentEmbeddingModel.document_id == DocumentModel.document_id,
                DocumentEmbeddingModel.chunk_content.ilike(like_query),
            ).exists()
            statement = statement.filter(or_(DocumentModel.filename.ilike(like_query), matching_chunk_exists))
        return statement

    def _accessible_documents_query(self):
        return self._apply_access_filter(self._session.query(DocumentModel).options(defer(DocumentModel.metadata_)))

    def _apply_access_filter(self, statement):
        if is_superadmin_user(self._current_user):
            return statement

        current_user_id = user_id(self._current_user)
        assignment = DocumentAssignmentModel
        active_assignment = select(1).where(
            assignment.document_id == DocumentModel.document_id,
            assignment.status.not_in(("CANCELLED", "EXPIRED")),
            or_(
                assignment.assigned_to_user_id == current_user_id,
                assignment.assigned_by_user_id == current_user_id,
            ),
        ).exists()
        owner_id = func.coalesce(DocumentModel.owner_user_id, DocumentModel.metadata_["owner_user_id"].astext)
        tenant_id = func.coalesce(DocumentModel.tenant_id, DocumentModel.metadata_["tenant_id"].astext)
        clauses = [owner_id == current_user_id, active_assignment]
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(tenant_id.in_(admin_tenant_ids))
        groups = user_groups(self._current_user)
        if groups:
            member_tenant_ids = [
                str(membership["tenant_id"])
                for membership in tenant_memberships(self._current_user)
                if membership.get("tenant_id")
            ]
            clauses.append(
                or_(tenant_id.is_(None), tenant_id.in_(member_tenant_ids))
                & or_(*(DocumentModel.metadata_.contains({"owner_groups": [group]}) for group in groups))
            )
        return statement.filter(or_(*clauses))

    def _sort_clause(self, sort: str):
        options = {
            "created_asc": DocumentModel.created_at.asc(),
            "created_desc": DocumentModel.created_at.desc(),
            "filename_asc": DocumentModel.filename.asc(),
            "filename_desc": DocumentModel.filename.desc(),
            "updated_desc": DocumentModel.updated_at.desc(),
        }
        return options.get(sort, DocumentModel.created_at.desc())

    def _with_summaries(self, statement, query: str | None = None):
        chunk = DocumentEmbeddingModel
        matches_document = chunk.document_id == DocumentModel.document_id
        count = select(func.count(chunk.chunk_id)).where(matches_document).correlate(DocumentModel).scalar_subquery()
        snippet = null()
        if query:
            snippet = (
                select(chunk.chunk_content)
                .where(matches_document, chunk.chunk_content.ilike(f"%{query}%"))
                .order_by(chunk.chunk_index.asc())
                .limit(1)
                .correlate(DocumentModel)
                .scalar_subquery()
            )
        return statement.add_columns(count.label("chunk_count"), snippet.label("snippet"))

    def _to_summary(self, document: DocumentModel, chunk_count: int, snippet: str | None) -> DocumentSummary:
        return DocumentSummary(
            document_id=str(document.document_id),
            filename=document.filename,
            mime_type=document.mime_type,
            status=document.status,
            chunk_count=chunk_count,
            processed_at=document.processed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
            snippet=snippet.strip()[:360] if snippet is not None else None,
        )
