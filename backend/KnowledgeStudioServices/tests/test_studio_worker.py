from __future__ import annotations

from typing import Any

from app.application.quota_guard import StudioQuotaGuard
from app.interfaces.worker import StudioWorker


class _FakeRepo:
    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self._jobs = list(jobs)
        self.finished: list[dict[str, Any]] = []

    def claim_next_pending_job(self) -> dict[str, Any] | None:
        return self._jobs.pop(0) if self._jobs else None

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
        self.finished.append(
            {
                "job_id": job_id,
                "status": status,
                "step": step,
                "error_code": error_code,
                "error_message": error_message,
                "usage_tokens": usage_tokens,
            }
        )


def test_studio_worker_processes_pending_job_and_updates_quota() -> None:
    repo = _FakeRepo(
        [
            {
                "job_id": "job-1",
                "tenant_id": "t-1",
                "collection_id": "col-1",
                "created_by_user_id": "u-1",
                "template_id": "summary.executive",
                "model_id": "openai/gpt-oss-20b",
                "options": {},
            }
        ]
    )
    guard = StudioQuotaGuard(daily_token_limit=5000, max_concurrent_jobs=2)

    worker = StudioWorker(
        repository=repo,
        quota_guard=guard,
        load_document_sources=lambda _t, _c: [("doc-1", "sha-1")],
        authorize_all_sources=lambda _t, _u, _docs: True,
        load_chunks=lambda _docs: {("doc-1", 0): "El contrato establece un plazo de 97 dias."},
        generate_json=lambda _req, _chunks, _errs: {
            "schema_version": "1.0.0",
            "template_id": "summary.executive",
            "title": "Resumen ejecutivo",
            "sections": [
                {
                    "id": "s1",
                    "heading": "Plazo",
                    "claims": [
                        {
                            "text": "El plazo es de 97 dias.",
                            "citations": [
                                {
                                    "document_id": "doc-1",
                                    "chunk_index": 0,
                                    "quote": "plazo de 97 dias",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        estimate_tokens=lambda _job: 1000,
    )

    result = worker.run_once()
    assert result is not None
    assert result.status == "SUCCEEDED"
    assert len(repo.finished) == 1
    assert repo.finished[0]["status"] == "SUCCEEDED"
    assert repo.finished[0]["usage_tokens"] == 1000
    assert guard.remaining_tokens("t-1") == 4000
    assert worker.run_once() is None


def test_studio_worker_rejects_job_when_quota_exceeded() -> None:
    repo = _FakeRepo(
        [
            {
                "job_id": "job-2",
                "tenant_id": "t-2",
                "collection_id": "col-1",
                "created_by_user_id": "u-1",
                "template_id": "summary.executive",
                "model_id": "openai/gpt-oss-20b",
                "options": {},
            }
        ]
    )
    guard = StudioQuotaGuard(daily_token_limit=500, max_concurrent_jobs=1)

    worker = StudioWorker(
        repository=repo,
        quota_guard=guard,
        load_document_sources=lambda _t, _c: [],
        authorize_all_sources=lambda _t, _u, _docs: True,
        load_chunks=lambda _docs: {},
        generate_json=lambda _req, _chunks, _errs: {},
        estimate_tokens=lambda _job: 1200,
    )

    result = worker.run_once()
    assert result is not None
    assert result.status == "FAILED"
    assert result.error_code == "DAILY_TOKEN_QUOTA"
    assert repo.finished[0]["step"] == "quota_rejected"

