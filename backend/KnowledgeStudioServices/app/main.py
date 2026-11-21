"""FastAPI HTTP entrypoint for KnowledgeStudioServices (R6-04), gated by STUDIO_ENABLED."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config.security import require_studio_user
from app.domain.artifacts import (
    P0_TEMPLATES,
    ArtifactContent,
    render_evidence_table_csv,
    validate_groundedness,
)
from app.domain.visuals_and_learning import (
    FlashcardState,
    build_concept_graph_from_wikilinks,
    extract_verified_chart_series,
    sanitize_mermaid_diagram,
    sm2_review,
)
from app.infrastructure.studio_repository_pg import StudioRepositoryPg


def is_studio_enabled() -> bool:
    return os.environ.get("STUDIO_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _require_enabled() -> None:
    if not is_studio_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Studio está deshabilitado (STUDIO_ENABLED=false).",
        )


app = FastAPI(title="Blandskron Knowledge Studio API", version="1.0.0")
_cors_raw = os.environ.get("CORS_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]')
try:
    _cors_origins = json.loads(_cors_raw) if isinstance(_cors_raw, str) else ["http://localhost:3000"]
except ValueError:
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_studio_repo() -> StudioRepositoryPg:
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL no configurada para Knowledge Studio.",
        )
    engine = create_engine(db_url, pool_pre_ping=True)
    return StudioRepositoryPg(Session(engine))


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "studio_enabled": is_studio_enabled(), "templates_count": len(P0_TEMPLATES)}


@app.get("/api/v1/studio/templates")
def list_templates() -> dict[str, Any]:
    _require_enabled()
    return {"templates": sorted(P0_TEMPLATES)}


class ValidateArtifactRequest(BaseModel):
    artifact: ArtifactContent
    chunks: dict[str, str] = Field(default_factory=dict)  # key format: "doc_id#chunk_index"


@app.post("/api/v1/studio/validate")
def validate_artifact_endpoint(payload: ValidateArtifactRequest) -> dict[str, Any]:
    _require_enabled()
    lookup: dict[tuple[str, int], str] = {}
    for key, text in payload.chunks.items():
        if "#" in key:
            doc_id, idx_str = key.rsplit("#", 1)
            if idx_str.isdigit():
                lookup[(doc_id, int(idx_str))] = text
    report = validate_groundedness(payload.artifact, lookup)
    return {
        "valid": report.valid,
        "score": report.score,
        "total_claims": report.total_claims,
        "anchored_claims": report.anchored_claims,
        "errors": report.errors,
    }


@app.post("/api/v1/studio/export-csv")
def export_csv_endpoint(artifact: ArtifactContent) -> dict[str, str]:
    _require_enabled()
    return {"csv": render_evidence_table_csv(artifact)}


class MermaidRequest(BaseModel):
    source: str


@app.post("/api/v1/studio/mermaid/validate")
def validate_mermaid_endpoint(payload: MermaidRequest) -> dict[str, str]:
    _require_enabled()
    try:
        clean = sanitize_mermaid_diagram(payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return {"status": "ok", "source": clean}


class ConceptGraphRequest(BaseModel):
    documents: list[dict[str, Any]]


@app.post("/api/v1/studio/graph")
def concept_graph_endpoint(payload: ConceptGraphRequest) -> dict[str, Any]:
    _require_enabled()
    return build_concept_graph_from_wikilinks(payload.documents)


class ChartSeriesRequest(BaseModel):
    artifact: ArtifactContent
    label_column: str
    value_column: str


@app.post("/api/v1/studio/chart-series")
def chart_series_endpoint(payload: ChartSeriesRequest) -> dict[str, Any]:
    _require_enabled()
    points = extract_verified_chart_series(payload.artifact, payload.label_column, payload.value_column)
    return {
        "points": [
            {"label": p.label, "value": p.value, "provenance": p.provenance}
            for p in points
        ]
    }


class Sm2ReviewRequest(BaseModel):
    card: FlashcardState
    quality: int = Field(ge=0, le=5)


@app.post("/api/v1/studio/flashcards/review")
def review_flashcard_endpoint(payload: Sm2ReviewRequest) -> dict[str, Any]:
    _require_enabled()
    updated = sm2_review(payload.card, payload.quality)
    return updated.model_dump()


class CreateCollectionRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=600)
    visibility: str = Field(default="private")


class CreateArtifactRequest(BaseModel):
    collection_id: str | None = None
    template_id: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    document_ids: list[str] = Field(min_length=1)
    content: ArtifactContent


class EnqueueJobRequest(BaseModel):
    collection_id: str
    template_id: str
    operation_key: str = Field(min_length=4, max_length=128)
    model_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/v1/studio/collections")
def list_collections_endpoint(user: dict[str, Any] = Depends(require_studio_user)) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    return {"items": repo.list_collections(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/collections", status_code=status.HTTP_201_CREATED)
def create_collection_endpoint(
    payload: CreateCollectionRequest,
    user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    return repo.create_collection(
        tenant_id=user["active_tenant_id"],
        owner_user_id=user["user_id"],
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
    )


@app.get("/api/v1/studio/jobs")
def list_jobs_endpoint(user: dict[str, Any] = Depends(require_studio_user)) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    return {"items": repo.list_jobs(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/jobs", status_code=status.HTTP_202_ACCEPTED)
def enqueue_job_endpoint(
    payload: EnqueueJobRequest,
    user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    _require_enabled()
    if payload.template_id not in P0_TEMPLATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plantilla P0 no soportada.")
    repo = _get_studio_repo()
    return repo.enqueue_job(
        tenant_id=user["active_tenant_id"],
        collection_id=payload.collection_id,
        created_by_user_id=user["user_id"],
        operation_key=payload.operation_key,
        template_id=payload.template_id,
        model_id=payload.model_id,
        options=payload.options,
    )


@app.post("/api/v1/studio/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str, user: dict[str, Any] = Depends(require_studio_user)) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    cancelled = repo.cancel_job(job_id=job_id, tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])
    return {"job_id": job_id, "cancelled": cancelled}


@app.get("/api/v1/studio/artifacts")
def list_artifacts_endpoint(user: dict[str, Any] = Depends(require_studio_user)) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    return {"items": repo.list_artifacts(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/artifacts", status_code=status.HTTP_201_CREATED)
def create_artifact_endpoint(
    payload: CreateArtifactRequest,
    user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    _require_enabled()
    if payload.template_id not in P0_TEMPLATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plantilla P0 no soportada.")
    repo = _get_studio_repo()
    collection_id = payload.collection_id
    if not collection_id:
        col = repo.create_collection(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            title=f"Colección {payload.title[:40]}",
        )
        collection_id = col["collection_id"]
    return repo.save_artifact(
        tenant_id=user["active_tenant_id"],
        owner_user_id=user["user_id"],
        collection_id=collection_id,
        template_id=payload.template_id,
        title=payload.title,
        content=payload.content.model_dump(),
        document_ids=payload.document_ids,
    )


@app.get("/api/v1/studio/artifacts/{artifact_id}")
def get_artifact_endpoint(artifact_id: str, user: dict[str, Any] = Depends(require_studio_user)) -> dict[str, Any]:
    _require_enabled()
    repo = _get_studio_repo()
    item = repo.get_artifact(artifact_id=artifact_id, tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefacto no encontrado.")
    return item

