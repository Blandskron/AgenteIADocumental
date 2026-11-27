"""Background worker loop for Knowledge Studio jobs (`FOR UPDATE SKIP LOCKED` + quotas, R8-05)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from app.application.quota_guard import QuotaExceededError, StudioQuotaGuard
from app.application.studio_runner import StudioJobRequest, StudioJobResult, execute_studio_job


class StudioJobQueueRepository(Protocol):
    def claim_next_pending_job(self) -> dict[str, Any] | None: ...

    def mark_job_finished(
        self,
        job_id: str,
        *,
        status: str,
        step: str = "done",
        error_code: str | None = None,
        error_message: str | None = None,
        usage_tokens: int = 0,
    ) -> None: ...


class StudioWorker:
    """Claims one job at a time, enforces per-tenant quotas, runs grounded generation and persists outcome."""

    def __init__(
        self,
        *,
        repository: StudioJobQueueRepository,
        quota_guard: StudioQuotaGuard,
        load_document_sources: Callable[[str, str], list[tuple[str, str]]],
        authorize_all_sources: Callable[[str, str, list[str]], bool],
        load_chunks: Callable[[list[str]], dict[tuple[str, int], str]],
        generate_json: Callable[[StudioJobRequest, dict[tuple[str, int], str], list[str] | None], dict[str, Any]],
        estimate_tokens: Callable[[dict[str, Any]], int] | None = None,
    ) -> None:
        self._repository = repository
        self._quota_guard = quota_guard
        self._load_document_sources = load_document_sources
        self._authorize_all_sources = authorize_all_sources
        self._load_chunks = load_chunks
        self._generate_json = generate_json
        self._estimate_tokens = estimate_tokens or (lambda _job: 1_500)

    def run_once(self) -> StudioJobResult | None:
        job = self._repository.claim_next_pending_job()
        if job is None:
            return None

        job_id = str(job["job_id"])
        tenant_id = str(job["tenant_id"])
        user_id = str(job["created_by_user_id"])
        collection_id = str(job["collection_id"])
        template_id = str(job["template_id"])
        model_id = str(job.get("model_id") or "openai/gpt-oss-20b")
        options = dict(job.get("options") or {})
        estimated_tokens = max(0, self._estimate_tokens(job))

        try:
            self._quota_guard.acquire_job_slot(tenant_id, estimated_tokens=estimated_tokens)
        except QuotaExceededError as exc:
            self._repository.mark_job_finished(
                job_id,
                status="FAILED",
                step="quota_rejected",
                error_code=exc.code,
                error_message=str(exc),
                usage_tokens=0,
            )
            return StudioJobResult(
                status="FAILED",
                cache_fingerprint="",
                error_code=exc.code,
                error_message=str(exc),
            )

        actual_tokens = 0
        try:
            sources = self._load_document_sources(tenant_id, collection_id)
            request = StudioJobRequest(
                tenant_id=tenant_id,
                user_id=user_id,
                collection_id=collection_id,
                template_id=template_id,
                model_id=model_id,
                document_sources=sources,
                options=options,
            )
            result = execute_studio_job(
                request,
                authorize_all_sources=self._authorize_all_sources,
                load_chunks=self._load_chunks,
                generate_json=self._generate_json,
            )
            actual_tokens = estimated_tokens if result.status == "SUCCEEDED" else 0
            if (
                result.status == "SUCCEEDED"
                and result.artifact is not None
                and callable(getattr(self._repository, "save_artifact", None))
            ):
                self._repository.save_artifact(  # type: ignore[attr-defined]
                    tenant_id=tenant_id,
                    owner_user_id=user_id,
                    collection_id=collection_id,
                    template_id=template_id,
                    title=result.artifact.title,
                    content=result.artifact.model_dump(),
                    document_ids=[doc_id for doc_id, _ in sources],
                    groundedness_score=result.groundedness.score if result.groundedness else 1.0,
                    job_id=job_id,
                    cache_fingerprint=result.cache_fingerprint,
                )
            self._repository.mark_job_finished(
                job_id,
                status=result.status,
                step="done" if result.status == "SUCCEEDED" else "failed",
                error_code=result.error_code,
                error_message=result.error_message,
                usage_tokens=actual_tokens,
            )
            return result
        finally:
            self._quota_guard.release_job_slot(tenant_id, actual_tokens=actual_tokens)

