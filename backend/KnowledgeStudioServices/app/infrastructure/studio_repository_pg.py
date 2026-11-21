"""Repository for Knowledge Studio tables (`studio.*`) using PostgreSQL SKIP LOCKED queue (R7-01 / STB-06)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


class StudioRepositoryPg:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_collection(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        title: str,
        description: str = "",
        visibility: str = "private",
        area_id: str | None = None,
    ) -> dict[str, Any]:
        collection_id = str(uuid4())
        self._session.execute(
            text("""
                INSERT INTO studio.collections (collection_id, tenant_id, owner_user_id, area_id, title, description, visibility)
                VALUES (:id, :tenant_id, :owner_user_id, :area_id, :title, :description, :visibility)
            """),
            {
                "id": collection_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "area_id": area_id,
                "title": title.strip(),
                "description": description.strip(),
                "visibility": visibility,
            },
        )
        self._session.commit()
        return {"collection_id": collection_id, "tenant_id": tenant_id, "title": title.strip(), "visibility": visibility}

    def list_collections(self, *, tenant_id: str, owner_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT collection_id, tenant_id, owner_user_id, title, description, visibility, created_at
                FROM studio.collections
                WHERE tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "owner_user_id": owner_user_id, "limit": max(1, min(100, limit))},
        ).mappings().all()
        return [dict(r) for r in rows]

    def enqueue_job(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        created_by_user_id: str,
        operation_key: str,
        template_id: str,
        model_id: str | None = None,
        options: dict[str, Any] | None = None,
        cache_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        existing = self._session.execute(
            text("""
                SELECT job_id, status, step FROM studio.studio_jobs
                WHERE tenant_id = :tenant_id AND operation_key = :operation_key
            """),
            {"tenant_id": tenant_id, "operation_key": operation_key},
        ).mappings().first()
        if existing is not None:
            return dict(existing)

        job_id = str(uuid4())
        self._session.execute(
            text("""
                INSERT INTO studio.studio_jobs (
                    job_id, tenant_id, collection_id, created_by_user_id, operation_key,
                    template_id, model_id, options, cache_fingerprint, status, step
                ) VALUES (
                    :job_id, :tenant_id, :collection_id, :created_by_user_id, :operation_key,
                    :template_id, :model_id, CAST(:options AS jsonb), :cache_fingerprint, 'PENDING', 'queued'
                )
            """),
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "created_by_user_id": created_by_user_id,
                "operation_key": operation_key,
                "template_id": template_id,
                "model_id": model_id,
                "options": json.dumps(options or {}),
                "cache_fingerprint": cache_fingerprint,
            },
        )
        self._session.commit()
        return {"job_id": job_id, "status": "PENDING", "step": "queued"}

    def list_jobs(self, *, tenant_id: str, owner_user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT job_id, collection_id, template_id, model_id, status, step,
                       error_code, error_message, usage_tokens, created_at, updated_at
                FROM studio.studio_jobs
                WHERE tenant_id = :tenant_id AND created_by_user_id = :owner_user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "owner_user_id": owner_user_id, "limit": max(1, min(100, limit))},
        ).mappings().all()
        return [dict(r) for r in rows]

    def cancel_job(self, *, job_id: str, tenant_id: str, owner_user_id: str) -> bool:
        result = self._session.execute(
            text("""
                UPDATE studio.studio_jobs
                SET cancel_requested = TRUE,
                    status = CASE WHEN status = 'PENDING' THEN 'CANCELLED' ELSE status END,
                    updated_at = :now
                WHERE job_id = :job_id
                  AND tenant_id = :tenant_id
                  AND created_by_user_id = :owner_user_id
                  AND status IN ('PENDING', 'RUNNING')
            """),
            {"job_id": job_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id, "now": datetime.now(UTC)},
        )
        self._session.commit()
        return bool(result.rowcount)

    def claim_next_pending_job(self) -> dict[str, Any] | None:
        """Atomically claims one PENDING job using PostgreSQL `FOR UPDATE SKIP LOCKED`."""
        row = self._session.execute(
            text("""
                WITH next_job AS (
                    SELECT job_id
                    FROM studio.studio_jobs
                    WHERE status = 'PENDING' AND cancel_requested = FALSE
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE studio.studio_jobs j
                SET status = 'RUNNING',
                    step = 'retrieving',
                    attempts = j.attempts + 1,
                    heartbeat_at = :now,
                    updated_at = :now
                FROM next_job
                WHERE j.job_id = next_job.job_id
                RETURNING j.job_id, j.tenant_id, j.collection_id, j.created_by_user_id,
                          j.template_id, j.model_id, j.options, j.attempts
            """),
            {"now": datetime.now(UTC)},
        ).mappings().first()
        self._session.commit()
        return dict(row) if row is not None else None

    def mark_job_finished(
        self,
        job_id: str,
        *,
        status: str,
        step: str = "done",
        error_code: str | None = None,
        error_message: str | None = None,
        usage_tokens: int = 0,
    ) -> None:
        self._session.execute(
            text("""
                UPDATE studio.studio_jobs
                SET status = :status,
                    step = :step,
                    error_code = :error_code,
                    error_message = :error_message,
                    usage_tokens = :usage_tokens,
                    updated_at = :now
                WHERE job_id = :job_id
            """),
            {
                "job_id": job_id,
                "status": status,
                "step": step,
                "error_code": error_code,
                "error_message": error_message,
                "usage_tokens": usage_tokens,
                "now": datetime.now(UTC),
            },
        )
        self._session.commit()

    def save_artifact(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        collection_id: str,
        template_id: str,
        title: str,
        content: dict[str, Any],
        document_ids: list[str],
        groundedness_score: float = 1.0,
    ) -> dict[str, Any]:
        artifact_id = str(uuid4())
        now = datetime.now(UTC)
        self._session.execute(
            text("""
                INSERT INTO studio.artifacts (
                    artifact_id, tenant_id, owner_user_id, collection_id,
                    template_id, title, content, status, version, groundedness_score,
                    created_at, updated_at
                ) VALUES (
                    :artifact_id, :tenant_id, :owner_user_id, :collection_id,
                    :template_id, :title, CAST(:content AS jsonb), 'FRESH', 1, :score,
                    :now, :now
                )
            """),
            {
                "artifact_id": artifact_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "collection_id": collection_id,
                "template_id": template_id,
                "title": title.strip()[:200],
                "content": json.dumps(content),
                "score": groundedness_score,
                "now": now,
            },
        )
        for doc_id in dict.fromkeys(document_ids):
            self._session.execute(
                text("""
                    INSERT INTO studio.artifact_sources (artifact_id, document_id)
                    VALUES (:artifact_id, :document_id)
                    ON CONFLICT DO NOTHING
                """),
                {"artifact_id": artifact_id, "document_id": doc_id},
            )
        self._session.commit()
        return {
            "artifact_id": artifact_id,
            "collection_id": collection_id,
            "template_id": template_id,
            "title": title.strip()[:200],
            "status": "FRESH",
            "version": 1,
            "groundedness_score": groundedness_score,
            "content": content,
            "document_ids": list(dict.fromkeys(document_ids)),
            "created_at": now.isoformat(),
        }

    def list_artifacts(self, *, tenant_id: str, owner_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT artifact_id, collection_id, template_id, title, status, version,
                       groundedness_score, content, created_at, updated_at
                FROM studio.artifacts
                WHERE tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                ORDER BY updated_at DESC
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "owner_user_id": owner_user_id, "limit": max(1, min(100, limit))},
        ).mappings().all()
        return [dict(r) for r in rows]

    def get_artifact(self, *, artifact_id: str, tenant_id: str, owner_user_id: str) -> dict[str, Any] | None:
        row = self._session.execute(
            text("""
                SELECT artifact_id, collection_id, template_id, title, status, version,
                       groundedness_score, content, created_at, updated_at
                FROM studio.artifacts
                WHERE artifact_id = :artifact_id
                  AND tenant_id = :tenant_id
                  AND owner_user_id = :owner_user_id
            """),
            {"artifact_id": artifact_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def search_authorized_documents(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT document_id, filename, mime_type, status, updated_at
                FROM public.documents
                WHERE tenant_id = :tenant_id
                  AND owner_user_id = :owner_user_id
                  AND (:q = '' OR filename ILIKE :pattern)
                ORDER BY updated_at DESC
                LIMIT :limit
            """),
            {
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "q": query,
                "pattern": f"%{query}%",
                "limit": max(1, min(20, limit)),
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    def get_authorized_document_chunks(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        document_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT e.chunk_id, e.document_id, e.chunk_index, e.chunk_content
                FROM public.document_embeddings e
                JOIN public.documents d ON d.document_id = e.document_id
                WHERE d.document_id = :document_id
                  AND d.tenant_id = :tenant_id
                  AND d.owner_user_id = :owner_user_id
                ORDER BY e.chunk_index ASC
                LIMIT :limit
            """),
            {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "limit": max(1, min(20, limit)),
            },
        ).mappings().all()
        return [dict(r) for r in rows]
