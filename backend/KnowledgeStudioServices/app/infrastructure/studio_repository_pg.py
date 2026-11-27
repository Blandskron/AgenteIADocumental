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
        artifact_id: str | None = None,
        job_id: str | None = None,
        cache_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        clean_title = title.strip()[:200]
        body_md = str(content.get("body_md") or "")
        version_id = str(uuid4())
        unique_doc_ids = list(dict.fromkeys(doc_id for doc_id in document_ids if doc_id))

        if artifact_id:
            updated = self._session.execute(
                text("""
                    UPDATE studio.artifacts
                    SET title = :title,
                        status = 'FRESH',
                        current_version = current_version + 1,
                        cache_fingerprint = COALESCE(:cache_fingerprint, cache_fingerprint),
                        updated_at = :now
                    WHERE artifact_id = :artifact_id
                      AND tenant_id = :tenant_id
                      AND owner_user_id = :owner_user_id
                    RETURNING artifact_id, collection_id, template_id, current_version, created_at
                """),
                {
                    "artifact_id": artifact_id,
                    "tenant_id": tenant_id,
                    "owner_user_id": owner_user_id,
                    "title": clean_title,
                    "cache_fingerprint": cache_fingerprint,
                    "now": now,
                },
            ).mappings().first()
            if updated is None:
                raise ValueError(f"Artefacto no encontrado para versionado: {artifact_id}")
            version_number = int(updated["current_version"])
            collection_id = str(updated["collection_id"])
            template_id = str(updated["template_id"])
            created_at = updated["created_at"]
        else:
            artifact_id = str(uuid4())
            version_number = 1
            created_at = now
            self._session.execute(
                text("""
                    INSERT INTO studio.artifacts (
                        artifact_id, tenant_id, collection_id, owner_user_id,
                        template_id, title, status, current_version, cache_fingerprint,
                        created_at, updated_at
                    ) VALUES (
                        :artifact_id, :tenant_id, :collection_id, :owner_user_id,
                        :template_id, :title, 'FRESH', 1, :cache_fingerprint,
                        :now, :now
                    )
                """),
                {
                    "artifact_id": artifact_id,
                    "tenant_id": tenant_id,
                    "collection_id": collection_id,
                    "owner_user_id": owner_user_id,
                    "template_id": template_id,
                    "title": clean_title,
                    "cache_fingerprint": cache_fingerprint,
                    "now": now,
                },
            )

        self._session.execute(
            text("""
                INSERT INTO studio.artifact_versions (
                    version_id, artifact_id, version_number, job_id,
                    created_by_user_id, content_json, body_md, groundedness_score,
                    created_at
                ) VALUES (
                    :version_id, :artifact_id, :version_number, :job_id,
                    :created_by_user_id, CAST(:content_json AS jsonb), :body_md, :groundedness_score,
                    :now
                )
            """),
            {
                "version_id": version_id,
                "artifact_id": artifact_id,
                "version_number": version_number,
                "job_id": job_id,
                "created_by_user_id": owner_user_id,
                "content_json": json.dumps(content),
                "body_md": body_md,
                "groundedness_score": groundedness_score,
                "now": now,
            },
        )
        for doc_id in unique_doc_ids:
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
            "version_id": version_id,
            "collection_id": collection_id,
            "template_id": template_id,
            "title": clean_title,
            "status": "FRESH",
            "version": version_number,
            "current_version": version_number,
            "groundedness_score": float(groundedness_score),
            "content": content,
            "body_md": body_md,
            "document_ids": unique_doc_ids,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            "updated_at": now.isoformat(),
        }

    def list_artifacts(self, *, tenant_id: str, owner_user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT a.artifact_id,
                       a.collection_id,
                       a.template_id,
                       a.title,
                       a.status,
                       a.current_version AS version,
                       a.current_version,
                       CAST(v.groundedness_score AS DOUBLE PRECISION) AS groundedness_score,
                       v.content_json AS content,
                       v.body_md,
                       a.created_at,
                       a.updated_at
                FROM studio.artifacts a
                JOIN studio.artifact_versions v
                  ON v.artifact_id = a.artifact_id
                 AND v.version_number = a.current_version
                WHERE a.tenant_id = :tenant_id AND a.owner_user_id = :owner_user_id
                ORDER BY a.updated_at DESC
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "owner_user_id": owner_user_id, "limit": max(1, min(100, limit))},
        ).mappings().all()
        return [dict(r) for r in rows]

    def get_artifact(
        self,
        *,
        artifact_id: str,
        tenant_id: str,
        owner_user_id: str,
        version_number: int | None = None,
    ) -> dict[str, Any] | None:
        row = self._session.execute(
            text("""
                SELECT a.artifact_id,
                       a.collection_id,
                       a.template_id,
                       a.title,
                       a.status,
                       v.version_number AS version,
                       a.current_version,
                       CAST(v.groundedness_score AS DOUBLE PRECISION) AS groundedness_score,
                       v.content_json AS content,
                       v.body_md,
                       a.created_at,
                       a.updated_at
                FROM studio.artifacts a
                JOIN studio.artifact_versions v
                  ON v.artifact_id = a.artifact_id
                 AND v.version_number = COALESCE(:version_number, a.current_version)
                WHERE a.artifact_id = :artifact_id
                  AND a.tenant_id = :tenant_id
                  AND a.owner_user_id = :owner_user_id
            """),
            {
                "artifact_id": artifact_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "version_number": version_number,
            },
        ).mappings().first()
        if row is None:
            return None
        item = dict(row)
        source_rows = self._session.execute(
            text("""
                SELECT document_id
                FROM studio.artifact_sources
                WHERE artifact_id = :artifact_id
                ORDER BY linked_at ASC
            """),
            {"artifact_id": artifact_id},
        ).scalars().all()
        item["document_ids"] = list(source_rows)
        return item

    def list_artifact_versions(
        self,
        *,
        artifact_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT v.version_id,
                       v.artifact_id,
                       v.version_number,
                       v.job_id,
                       v.created_by_user_id,
                       CAST(v.groundedness_score AS DOUBLE PRECISION) AS groundedness_score,
                       v.created_at
                FROM studio.artifact_versions v
                JOIN studio.artifacts a ON a.artifact_id = v.artifact_id
                WHERE v.artifact_id = :artifact_id
                  AND a.tenant_id = :tenant_id
                  AND a.owner_user_id = :owner_user_id
                ORDER BY v.version_number DESC
            """),
            {"artifact_id": artifact_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).mappings().all()
        return [dict(r) for r in rows]

    def search_authorized_documents(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        query: str,
        limit: int = 10,
        is_superuser: bool = False,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT DISTINCT d.document_id, d.filename, d.mime_type, d.status, d.updated_at
                FROM public.documents d
                LEFT JOIN public.document_embeddings e ON e.document_id = d.document_id
                LEFT JOIN public.document_assignments a
                  ON a.document_id = d.document_id
                 AND a.status NOT IN ('CANCELLED', 'EXPIRED')
                 AND (a.assigned_to_user_id = :owner_user_id OR a.assigned_by_user_id = :owner_user_id)
                WHERE (:is_superuser = TRUE OR (d.tenant_id = :tenant_id AND (d.owner_user_id = :owner_user_id OR a.document_id IS NOT NULL)))
                  AND (
                      :q = ''
                      OR d.filename ILIKE :pattern
                      OR (e.content_tsv IS NOT NULL AND e.content_tsv @@ websearch_to_tsquery('spanish', :q))
                  )
                ORDER BY d.updated_at DESC
                LIMIT :limit
            """),
            {
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "is_superuser": is_superuser,
                "q": query,
                "pattern": f"%{query}%",
                "limit": max(1, min(20, limit)),
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    def search_authorized_chunks_hybrid(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        query: str,
        document_ids: list[str] | None = None,
        limit: int = 8,
        is_superuser: bool = False,
    ) -> list[dict[str, Any]]:
        clean_query = (query or "").strip()
        if not clean_query:
            return []
        doc_filter = "AND d.document_id = ANY(:document_ids)" if document_ids else ""
        rows = self._session.execute(
            text(
                f"""
                SELECT e.chunk_id,
                       e.document_id,
                       d.filename,
                       e.chunk_index,
                       e.chunk_content,
                       COALESCE(
                           CASE WHEN e.content_tsv IS NOT NULL
                                THEN ts_rank_cd(e.content_tsv, websearch_to_tsquery('spanish', :q))
                                ELSE 0.0
                           END,
                           0.0
                       ) + CASE WHEN e.chunk_content ILIKE :pattern THEN 0.25 ELSE 0.0 END AS relevance_score
                FROM public.document_embeddings e
                JOIN public.documents d ON d.document_id = e.document_id
                LEFT JOIN public.document_assignments a
                  ON a.document_id = d.document_id
                 AND a.status NOT IN ('CANCELLED', 'EXPIRED')
                 AND (a.assigned_to_user_id = :owner_user_id OR a.assigned_by_user_id = :owner_user_id)
                WHERE (:is_superuser = TRUE OR (d.tenant_id = :tenant_id AND (d.owner_user_id = :owner_user_id OR a.document_id IS NOT NULL)))
                  {doc_filter}
                  AND (
                      (e.content_tsv IS NOT NULL AND e.content_tsv @@ websearch_to_tsquery('spanish', :q))
                      OR e.chunk_content ILIKE :pattern
                      OR d.filename ILIKE :pattern
                  )
                ORDER BY relevance_score DESC, e.chunk_index ASC
                LIMIT :limit
                """
            ),
            {
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "is_superuser": is_superuser,
                "q": clean_query,
                "pattern": f"%{clean_query}%",
                "document_ids": list(document_ids or []),
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
        is_superuser: bool = False,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT e.chunk_id, e.document_id, e.chunk_index, e.chunk_content
                FROM public.document_embeddings e
                JOIN public.documents d ON d.document_id = e.document_id
                LEFT JOIN public.document_assignments a
                  ON a.document_id = d.document_id
                 AND a.status NOT IN ('CANCELLED', 'EXPIRED')
                 AND (a.assigned_to_user_id = :owner_user_id OR a.assigned_by_user_id = :owner_user_id)
                WHERE d.document_id = :document_id
                  AND (:is_superuser = TRUE OR (d.tenant_id = :tenant_id AND (d.owner_user_id = :owner_user_id OR a.document_id IS NOT NULL)))
                ORDER BY e.chunk_index ASC
                LIMIT :limit
            """),
            {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "is_superuser": is_superuser,
                "limit": max(1, min(20, limit)),
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    def record_mcp_audit_event(
        self,
        *,
        action: str,
        actor_user_id: str,
        tenant_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            self._session.execute(
                text("""
                    INSERT INTO public.audit_logs (
                        audit_id, tenant_id, actor_user_id, action, resource_type, metadata, created_at
                    ) VALUES (
                        :audit_id, :tenant_id, :actor_user_id, :action, 'mcp_tool', CAST(:metadata AS jsonb), :now
                    )
                """),
                {
                    "audit_id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "actor_user_id": actor_user_id,
                    "action": action[:120],
                    "metadata": json.dumps(metadata or {}),
                    "now": datetime.now(UTC),
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
