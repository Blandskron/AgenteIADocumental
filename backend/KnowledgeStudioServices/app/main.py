"""FastAPI HTTP entrypoint for KnowledgeStudioServices (R6-04), gated by STUDIO_ENABLED."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
import json
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

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
from app.interfaces.mcp_readonly import ReadOnlyMcpDispatcher
from app.interfaces.mcp_server import handle_mcp_jsonrpc, validate_mcp_origin


def is_studio_enabled() -> bool:
    return os.environ.get("STUDIO_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _require_enabled() -> None:
    if not is_studio_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Studio está deshabilitado (STUDIO_ENABLED=false).",
        )


_engine: Engine | None = None
_engine_url: str | None = None
_session_factory: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _engine, _engine_url, _session_factory
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL no configurada para Knowledge Studio.",
        )
    if _engine is None or _engine_url != db_url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=int(os.environ.get("DB_POOL_MIN_SIZE", "2")),
            max_overflow=int(os.environ.get("DB_POOL_MAX_SIZE", "8")),
        )
        _engine_url = db_url
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    assert _session_factory is not None
    return _session_factory


def _dispose_engine() -> None:
    global _engine, _engine_url, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    _session_factory = None


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if (os.environ.get("DATABASE_URL") or "").strip():
        _get_session_factory()
    try:
        yield
    finally:
        _dispose_engine()


app = FastAPI(title="Blandskron Knowledge Studio API", version="1.0.0", lifespan=_lifespan)
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


def _get_studio_repo() -> Generator[StudioRepositoryPg, None, None]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield StudioRepositoryPg(session)
    finally:
        session.close()


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "studio_enabled": is_studio_enabled(), "templates_count": len(P0_TEMPLATES)}


@app.get("/api/v1/studio/templates")
def list_templates(
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    return {"templates": sorted(P0_TEMPLATES)}


class ValidateArtifactRequest(BaseModel):
    artifact: ArtifactContent
    chunks: dict[str, str] = Field(default_factory=dict)  # key format: "doc_id#chunk_index"


@app.post("/api/v1/studio/validate")
def validate_artifact_endpoint(
    payload: ValidateArtifactRequest,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
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
def export_csv_endpoint(
    artifact: ArtifactContent,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, str]:
    return {"csv": render_evidence_table_csv(artifact)}


class MermaidRequest(BaseModel):
    source: str


@app.post("/api/v1/studio/mermaid/validate")
def validate_mermaid_endpoint(
    payload: MermaidRequest,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, str]:
    try:
        clean = sanitize_mermaid_diagram(payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return {"status": "ok", "source": clean}


class ConceptGraphRequest(BaseModel):
    documents: list[dict[str, Any]]


@app.post("/api/v1/studio/graph")
def concept_graph_endpoint(
    payload: ConceptGraphRequest,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    return build_concept_graph_from_wikilinks(payload.documents)


class ChartSeriesRequest(BaseModel):
    artifact: ArtifactContent
    label_column: str
    value_column: str


@app.post("/api/v1/studio/chart-series")
def chart_series_endpoint(
    payload: ChartSeriesRequest,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
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
def review_flashcard_endpoint(
    payload: Sm2ReviewRequest,
    _: None = Depends(_require_enabled),
    _user: dict[str, Any] = Depends(require_studio_user),
) -> dict[str, Any]:
    updated = sm2_review(payload.card, payload.quality)
    return updated.model_dump()


class CreateCollectionRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=600)
    visibility: str = Field(default="private")


class CreateArtifactRequest(BaseModel):
    artifact_id: str | None = None
    collection_id: str | None = None
    template_id: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    document_ids: list[str] = Field(default_factory=list)
    content: ArtifactContent
    groundedness_score: float = Field(default=1.0, ge=0.0, le=1.0)


class EnqueueJobRequest(BaseModel):
    collection_id: str
    template_id: str
    operation_key: str = Field(min_length=4, max_length=128)
    model_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/v1/studio/collections")
def list_collections_endpoint(
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    return {"items": repo.list_collections(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/collections", status_code=status.HTTP_201_CREATED)
def create_collection_endpoint(
    payload: CreateCollectionRequest,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    return repo.create_collection(
        tenant_id=user["active_tenant_id"],
        owner_user_id=user["user_id"],
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
    )


@app.get("/api/v1/studio/jobs")
def list_jobs_endpoint(
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    return {"items": repo.list_jobs(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/jobs", status_code=status.HTTP_202_ACCEPTED)
def enqueue_job_endpoint(
    payload: EnqueueJobRequest,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    if payload.template_id not in P0_TEMPLATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plantilla P0 no soportada.")
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
def cancel_job_endpoint(
    job_id: str,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    cancelled = repo.cancel_job(job_id=job_id, tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])
    return {"job_id": job_id, "cancelled": cancelled}


@app.get("/api/v1/studio/artifacts")
def list_artifacts_endpoint(
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    return {"items": repo.list_artifacts(tenant_id=user["active_tenant_id"], owner_user_id=user["user_id"])}


@app.post("/api/v1/studio/artifacts", status_code=status.HTTP_201_CREATED)
def create_artifact_endpoint(
    payload: CreateArtifactRequest,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    if payload.template_id not in P0_TEMPLATES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plantilla P0 no soportada.")
    collection_id = payload.collection_id
    if not collection_id and not payload.artifact_id:
        col = repo.create_collection(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            title=f"Colección {payload.title[:40]}",
        )
        collection_id = col["collection_id"]
    try:
        return repo.save_artifact(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            collection_id=collection_id or "",
            template_id=payload.template_id,
            title=payload.title,
            content=payload.content.model_dump(),
            document_ids=payload.document_ids,
            groundedness_score=payload.groundedness_score,
            artifact_id=payload.artifact_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@app.get("/api/v1/studio/artifacts/{artifact_id}")
def get_artifact_endpoint(
    artifact_id: str,
    version: int | None = None,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    item = repo.get_artifact(
        artifact_id=artifact_id,
        tenant_id=user["active_tenant_id"],
        owner_user_id=user["user_id"],
        version_number=version,
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefacto no encontrado.")
    return item


@app.get("/api/v1/studio/artifacts/{artifact_id}/versions")
def list_artifact_versions_endpoint(
    artifact_id: str,
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    items = repo.list_artifact_versions(
        artifact_id=artifact_id,
        tenant_id=user["active_tenant_id"],
        owner_user_id=user["user_id"],
    )
    return {"items": items}


def _build_live_mcp_dispatcher(repo: StudioRepositoryPg) -> ReadOnlyMcpDispatcher:
    def _search_documents(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        limit = int(args.get("limit") or 10)
        rows = repo.search_authorized_documents(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            query=query,
            limit=limit,
            is_superuser=bool(user.get("is_superuser")),
        )
        repo.record_mcp_audit_event(
            action="mcp.search_documents",
            actor_user_id=user["user_id"],
            tenant_id=user.get("active_tenant_id"),
            metadata={"count": len(rows)},
        )
        return {"items": rows, "count": len(rows)}

    def _search_documents_hybrid(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        limit = int(args.get("limit") or 8)
        raw_doc_ids = args.get("document_ids")
        doc_ids = [str(d) for d in raw_doc_ids] if isinstance(raw_doc_ids, list) else None
        rows = repo.search_authorized_chunks_hybrid(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            query=query,
            document_ids=doc_ids,
            limit=limit,
            is_superuser=bool(user.get("is_superuser")),
        )
        repo.record_mcp_audit_event(
            action="mcp.search_documents_hybrid",
            actor_user_id=user["user_id"],
            tenant_id=user.get("active_tenant_id"),
            metadata={"count": len(rows)},
        )
        return {"items": rows, "count": len(rows)}

    def _get_document_chunks(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        doc_id = str(args.get("document_id") or "").strip()
        limit = int(args.get("limit") or 10)
        rows = repo.get_authorized_document_chunks(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            document_id=doc_id,
            limit=limit,
            is_superuser=bool(user.get("is_superuser")),
        )
        repo.record_mcp_audit_event(
            action="mcp.get_document_chunks",
            actor_user_id=user["user_id"],
            tenant_id=user.get("active_tenant_id"),
            metadata={"document_id": doc_id, "count": len(rows)},
        )
        return {"document_id": doc_id, "chunks": rows}

    def _list_studio_artifacts(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit") or 10)
        rows = repo.list_artifacts(
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
            limit=limit,
        )
        repo.record_mcp_audit_event(
            action="mcp.list_studio_artifacts",
            actor_user_id=user["user_id"],
            tenant_id=user.get("active_tenant_id"),
            metadata={"count": len(rows)},
        )
        return {"items": rows, "count": len(rows)}

    def _get_studio_artifact(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        artifact_id = str(args.get("artifact_id") or "").strip()
        item = repo.get_artifact(
            artifact_id=artifact_id,
            tenant_id=user["active_tenant_id"],
            owner_user_id=user["user_id"],
        )
        repo.record_mcp_audit_event(
            action="mcp.get_studio_artifact",
            actor_user_id=user["user_id"],
            tenant_id=user.get("active_tenant_id"),
            metadata={"artifact_id": artifact_id, "found": item is not None},
        )
        return {"artifact": item}

    return ReadOnlyMcpDispatcher(
        {
            "search_documents": _search_documents,
            "search_documents_hybrid": _search_documents_hybrid,
            "get_document_chunks": _get_document_chunks,
            "list_studio_artifacts": _list_studio_artifacts,
            "get_studio_artifact": _get_studio_artifact,
        }
    )


@app.post("/api/v1/mcp")
def mcp_jsonrpc_endpoint(
    payload: dict[str, Any],
    origin: str | None = Header(default=None),
    _: None = Depends(_require_enabled),
    user: dict[str, Any] = Depends(require_studio_user),
    repo: StudioRepositoryPg = Depends(_get_studio_repo),
) -> dict[str, Any]:
    if not validate_mcp_origin(origin, _cors_origins):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origen no autorizado para MCP Streamable HTTP.",
        )
    dispatcher = _build_live_mcp_dispatcher(repo)
    return handle_mcp_jsonrpc(payload, dispatcher=dispatcher, current_user=user)

