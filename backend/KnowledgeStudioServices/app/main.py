"""FastAPI HTTP entrypoint for KnowledgeStudioServices (R6-04), gated by STUDIO_ENABLED."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

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


def is_studio_enabled() -> bool:
    return os.environ.get("STUDIO_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _require_enabled() -> None:
    if not is_studio_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Studio está deshabilitado (STUDIO_ENABLED=false).",
        )


app = FastAPI(title="Blandskron Knowledge Studio API", version="1.0.0")


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

