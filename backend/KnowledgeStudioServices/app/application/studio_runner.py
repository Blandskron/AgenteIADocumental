"""Studio job runner & access-revalidation engine (R4-02)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.artifacts import (
    ArtifactContent,
    GroundednessReport,
    compute_cache_fingerprint,
    validate_groundedness,
)


class StudioAccessRevokedError(PermissionError):
    code = "ACCESS_REVOKED"


class StudioValidationError(ValueError):
    code = "VALIDATION_FAILED"


@dataclass(frozen=True)
class StudioJobRequest:
    tenant_id: str
    user_id: str
    collection_id: str
    template_id: str
    model_id: str
    document_sources: list[tuple[str, str]]  # (document_id, content_sha256)
    options: dict[str, Any]


@dataclass(frozen=True)
class StudioJobResult:
    status: str  # "SUCCEEDED" | "FAILED" | "CANCELLED"
    cache_fingerprint: str
    artifact: ArtifactContent | None = None
    groundedness: GroundednessReport | None = None
    error_code: str | None = None
    error_message: str | None = None


def execute_studio_job(
    request: StudioJobRequest,
    *,
    authorize_all_sources: Callable[[str, str, list[str]], bool],
    load_chunks: Callable[[list[str]], dict[tuple[str, int], str]],
    generate_json: Callable[[StudioJobRequest, dict[tuple[str, int], str], list[str] | None], dict[str, Any]],
    is_cancelled: Callable[[], bool] | None = None,
) -> StudioJobResult:
    """Runs a Knowledge Studio generation job with strict pre/post access revalidation and max 1 auto-repair."""
    doc_ids = [doc_id for doc_id, _ in request.document_sources]
    fingerprint = compute_cache_fingerprint(
        request.document_sources,
        request.template_id,
        "1.0.0",
        request.model_id,
        request.options,
    )

    if not authorize_all_sources(request.tenant_id, request.user_id, doc_ids):
        return StudioJobResult(
            status="FAILED",
            cache_fingerprint=fingerprint,
            error_code="ACCESS_REVOKED",
            error_message="El usuario ya no tiene acceso a todas las fuentes de la colección.",
        )

    if is_cancelled and is_cancelled():
        return StudioJobResult(status="CANCELLED", cache_fingerprint=fingerprint)

    chunks = load_chunks(doc_ids)

    # Revalidate access right before generation (detects mid-flight revocation).
    if not authorize_all_sources(request.tenant_id, request.user_id, doc_ids):
        return StudioJobResult(
            status="FAILED",
            cache_fingerprint=fingerprint,
            error_code="ACCESS_REVOKED",
            error_message="Acceso revocado durante la generación del artefacto.",
        )

    last_errors: list[str] | None = None
    for attempt in range(2):  # Initial attempt + at most 1 bounded repair
        if is_cancelled and is_cancelled():
            return StudioJobResult(status="CANCELLED", cache_fingerprint=fingerprint)
        raw_payload = generate_json(request, chunks, last_errors)
        try:
            artifact = ArtifactContent.model_validate(raw_payload)
        except Exception as exc:
            last_errors = [str(exc)]
            continue
        report = validate_groundedness(artifact, chunks)
        if report.valid:
            return StudioJobResult(
                status="SUCCEEDED",
                cache_fingerprint=fingerprint,
                artifact=artifact,
                groundedness=report,
            )
        last_errors = report.errors

    return StudioJobResult(
        status="FAILED",
        cache_fingerprint=fingerprint,
        error_code="GROUNDEDNESS_FAILED",
        error_message="; ".join(last_errors or ["Artifact failed validation."]),
    )

