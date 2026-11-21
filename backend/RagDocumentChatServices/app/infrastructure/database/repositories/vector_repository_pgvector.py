from sqlalchemy import bindparam, func, literal, or_, select
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.domain.embeddings import SearchResult
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentEmbeddingModel, DocumentModel
from app.infrastructure.database.types import Vector

RRF_K = 60


def fuse_reciprocal_rank(
    vector_results: list[SearchResult],
    fts_results: list[SearchResult],
    limit: int,
    k: int = RRF_K,
) -> list[SearchResult]:
    """Combines vector and FTS rankings using Reciprocal Rank Fusion (RRF)."""
    if not fts_results:
        return vector_results[:limit]
    if not vector_results:
        return fts_results[:limit]

    rrf_scores: dict[str, float] = {}
    items: dict[str, SearchResult] = {}
    for rank, item in enumerate(vector_results, start=1):
        rrf_scores[item.chunk_id] = rrf_scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
        items.setdefault(item.chunk_id, item)
    for rank, item in enumerate(fts_results, start=1):
        rrf_scores[item.chunk_id] = rrf_scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
        items.setdefault(item.chunk_id, item)

    ordered_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:limit]
    return [items[cid] for cid in ordered_ids]


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
        query_text: str | None = None,
    ) -> list[SearchResult]:
        candidate_limit = max(limit * 3, limit)
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
        vector_rows = statement.filter(score >= min_score).order_by(distance.asc()).limit(candidate_limit).all()
        vector_results = [
            SearchResult(
                document_id=str(row.document_id),
                chunk_id=str(row.chunk_id),
                chunk_index=row.chunk_index,
                content=row.chunk_content,
                score=float(row.score),
                filename=(row.chunk_metadata or {}).get("filename"),
                metadata=row.chunk_metadata or {},
            )
            for row in vector_rows
        ]

        clean_query = (query_text or "").strip()
        if not clean_query:
            return vector_results[:limit]

        ts_query = func.websearch_to_tsquery("spanish", clean_query)
        fts_rank = func.ts_rank_cd(DocumentEmbeddingModel.content_tsv, ts_query).label("fts_rank")
        fts_stmt = self._session.query(
            DocumentEmbeddingModel.chunk_id,
            DocumentEmbeddingModel.document_id,
            DocumentEmbeddingModel.chunk_index,
            DocumentEmbeddingModel.chunk_content,
            DocumentEmbeddingModel.metadata_.label("chunk_metadata"),
            fts_rank,
        ).join(DocumentModel, DocumentEmbeddingModel.document_id == DocumentModel.document_id)
        fts_stmt = self._apply_access_filter(fts_stmt)
        if document_ids:
            fts_stmt = fts_stmt.filter(DocumentEmbeddingModel.document_id.in_(document_ids))
        fts_rows = (
            fts_stmt.filter(DocumentEmbeddingModel.content_tsv.op("@@")(ts_query))
            .order_by(fts_rank.desc())
            .limit(candidate_limit)
            .all()
        )

        fts_results = [
            SearchResult(
                document_id=str(row.document_id),
                chunk_id=str(row.chunk_id),
                chunk_index=row.chunk_index,
                content=row.chunk_content,
                score=float(row.fts_rank),
                filename=(row.chunk_metadata or {}).get("filename"),
                metadata=row.chunk_metadata or {},
            )
            for row in fts_rows
        ]
        return fuse_reciprocal_rank(vector_results, fts_results, limit=limit)

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
        # Interleave document positions so the prompt cap does not favor the first selected file.
        return sorted(results, key=lambda result: result.chunk_index)

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
