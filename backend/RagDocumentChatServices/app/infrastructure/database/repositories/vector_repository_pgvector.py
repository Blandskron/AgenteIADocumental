from sqlalchemy import bindparam, literal, or_, select
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, user_groups, user_id
from app.domain.embeddings import SearchResult
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentEmbeddingModel, DocumentModel
from app.infrastructure.database.types import Vector


class VectorRepositoryPgVector:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._current_user = current_user

    def search_similar(
        self,
        query_vector: list[float],
        limit: int,
        min_score: float = 0.0,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        query_vector_param = bindparam("query_vector", query_vector, type_=Vector(384))
        distance = DocumentEmbeddingModel.embedding.op("<=>")(query_vector_param)
        score = (literal(1.0) - distance).label("score")
        statement = self._session.query(
            DocumentEmbeddingModel.chunk_id,
            DocumentEmbeddingModel.document_id,
            DocumentEmbeddingModel.chunk_index,
            DocumentEmbeddingModel.chunk_content,
            DocumentEmbeddingModel.metadata_.label("chunk_metadata"),
            score,
        ).join(DocumentModel, DocumentEmbeddingModel.document_id == DocumentModel.document_id)
        statement = self._apply_access_filter(statement)
        if document_ids:
            statement = statement.filter(DocumentEmbeddingModel.document_id.in_(document_ids))
        rows = statement.filter(score >= min_score).order_by(distance.asc()).limit(limit).all()
        return [
            SearchResult(
                document_id=str(row.document_id),
                chunk_id=str(row.chunk_id),
                chunk_index=row.chunk_index,
                content=row.chunk_content,
                score=float(row.score),
                filename=(row.chunk_metadata or {}).get("filename"),
                metadata=row.chunk_metadata or {},
            )
            for row in rows
        ]

    def get_document_chunks(
        self,
        document_ids: list[str],
        limit_per_document: int,
    ) -> list[SearchResult]:
        unique_ids = list(dict.fromkeys(document_ids))
        if not unique_ids:
            return []

        results: list[SearchResult] = []
        for document_id in unique_ids:
            statement = self._session.query(
                DocumentEmbeddingModel.chunk_id,
                DocumentEmbeddingModel.document_id,
                DocumentEmbeddingModel.chunk_index,
                DocumentEmbeddingModel.chunk_content,
                DocumentEmbeddingModel.metadata_.label("chunk_metadata"),
            ).join(DocumentModel, DocumentEmbeddingModel.document_id == DocumentModel.document_id)
            statement = self._apply_access_filter(statement)
            rows = (
                statement.filter(DocumentEmbeddingModel.document_id == document_id)
                .order_by(DocumentEmbeddingModel.chunk_index.asc())
                .limit(limit_per_document)
                .all()
            )
            results.extend(
                SearchResult(
                    document_id=str(row.document_id),
                    chunk_id=str(row.chunk_id),
                    chunk_index=row.chunk_index,
                    content=row.chunk_content,
                    score=1.0,
                    filename=(row.chunk_metadata or {}).get("filename"),
                    metadata=row.chunk_metadata or {},
                )
                for row in rows
            )
        return results

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
        clauses = [
            DocumentModel.owner_user_id == current_user_id,
            DocumentModel.metadata_["owner_user_id"].astext == current_user_id,
            active_assignment,
        ]
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(DocumentModel.tenant_id.in_(admin_tenant_ids))
            clauses.append(DocumentModel.metadata_["tenant_id"].astext.in_(admin_tenant_ids))
        for group in user_groups(self._current_user):
            clauses.append(DocumentModel.metadata_.contains({"owner_groups": [group]}))
        return statement.filter(or_(*clauses))
