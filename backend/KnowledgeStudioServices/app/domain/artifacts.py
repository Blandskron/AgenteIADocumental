"""Knowledge Studio P0 — Schemas Pydantic v2, validador estricto de groundedness y 4 plantillas P0 (R4-03)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import re
from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, Field

P0_TEMPLATES = {
    "summary.executive",
    "summary.sectioned",
    "summary.comparative",
    "report.technical",
    "report.exec_memo",
    "report.study_guide",
    "report.glossary",
    "report.faq",
    "report.minutes",
    "report.risk_analysis",
    "evidence_table",
    "proposed_tasks",
}


class Citation(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)
    chunk_index: int = Field(ge=0)
    quote_text: str = Field(min_length=3, max_length=600)


class FactualClaim(BaseModel):
    statement: str = Field(min_length=3, max_length=1200)
    citations: list[Citation] = Field(default_factory=list)


class InferenceItem(BaseModel):
    statement: str = Field(min_length=3, max_length=1200)
    basis: str = Field(default="Inferencia sobre el contexto autorizado", max_length=400)


class EvidenceRow(BaseModel):
    cells: dict[str, str]
    citations: list[Citation] = Field(default_factory=list)
    verified: bool = True


class ProposedTask(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    owner: str | None = Field(default=None, max_length=120)
    owner_inferred: bool = False
    due_date: str | None = Field(default=None, max_length=64)
    status: Literal["proposed", "accepted", "rejected", "done"] = "proposed"
    citations: list[Citation] = Field(default_factory=list)


class ArtifactContent(BaseModel):
    template_id: str
    template_version: str = "1.0.0"
    title: str = Field(min_length=2, max_length=200)
    body_md: str = Field(default="", max_length=32000)
    claims: list[FactualClaim] = Field(default_factory=list)
    inferences: list[InferenceItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[EvidenceRow] = Field(default_factory=list)
    tasks: list[ProposedTask] = Field(default_factory=list)


@dataclass(frozen=True)
class GroundednessReport:
    valid: bool
    score: float
    total_claims: int
    anchored_claims: int
    errors: list[str]


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def validate_groundedness(
    artifact: ArtifactContent,
    chunk_lookup: dict[tuple[str, int], str],
    min_score: float = 0.95,
) -> GroundednessReport:
    """Verifies that every factual claim / citation anchors to real chunk text."""
    errors: list[str] = []
    if artifact.template_id not in P0_TEMPLATES:
        errors.append(f"Unsupported P0 template_id: {artifact.template_id}")

    total_claims = len(artifact.claims)
    anchored_claims = 0

    for idx, claim in enumerate(artifact.claims):
        if not claim.citations:
            errors.append(f"Claim #{idx + 1} lacks citations (must be cited or moved to inferences[]).")
            continue
        claim_anchored = False
        for cit in claim.citations:
            chunk_text = chunk_lookup.get((cit.document_id, cit.chunk_index))
            if chunk_text is None:
                errors.append(f"Citation points to unknown chunk ({cit.document_id}#{cit.chunk_index}).")
                continue
            if _norm(cit.quote_text) in _norm(chunk_text):
                claim_anchored = True
            else:
                errors.append(
                    f"Citation quote does not match chunk ({cit.document_id}#{cit.chunk_index})."
                )
        if claim_anchored:
            anchored_claims += 1

    # Validate evidence table rows
    for row_idx, row in enumerate(artifact.table_rows):
        if row.verified and not row.citations:
            errors.append(f"Table row #{row_idx + 1} marked verified=True without citations.")
        for cit in row.citations:
            chunk_text = chunk_lookup.get((cit.document_id, cit.chunk_index))
            if chunk_text is None or _norm(cit.quote_text) not in _norm(chunk_text):
                errors.append(f"Table row #{row_idx + 1} citation failed anchor check.")

    # Validate proposed tasks never auto-execute external actions and stay cited
    for task_idx, task in enumerate(artifact.tasks):
        if task.status != "proposed":
            errors.append(f"Generated task #{task_idx + 1} must start with status='proposed'.")
        if not task.citations:
            errors.append(f"Proposed task #{task_idx + 1} lacks source citation.")

    if artifact.template_id == "evidence_table":
        if not artifact.table_rows:
            errors.append("Artifact of type evidence_table requires at least one evidence row.")
            score = 0.0
        elif total_claims > 0:
            score = anchored_claims / total_claims
        else:
            score = 1.0 if not errors else 0.0
    elif artifact.template_id == "proposed_tasks":
        if not artifact.tasks:
            errors.append("Artifact of type proposed_tasks requires at least one proposed task.")
            score = 0.0
        elif total_claims > 0:
            score = anchored_claims / total_claims
        else:
            score = 1.0 if not errors else 0.0
    else:
        if total_claims == 0:
            errors.append("Artifact requires at least one cited factual claim.")
            score = 0.0
        else:
            score = anchored_claims / total_claims

    valid = (len(errors) == 0) and (score >= min_score)
    return GroundednessReport(
        valid=valid,
        score=round(score, 4),
        total_claims=total_claims,
        anchored_claims=anchored_claims,
        errors=errors,
    )


def compute_cache_fingerprint(
    sources: list[tuple[str, str]],
    template_id: str,
    template_version: str,
    model_id: str,
    options: dict[str, Any] | None = None,
) -> str:
    payload = {
        "sources": sorted((doc_id, sha) for doc_id, sha in sources),
        "template_id": template_id,
        "template_version": template_version,
        "model_id": model_id,
        "options": options or {},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_evidence_table_csv(artifact: ArtifactContent) -> str:
    """Exports verified evidence_table rows to CSV with explicit provenance columns and formula-injection neutralization."""
    buf = io.StringIO()
    columns = list(artifact.table_columns) + ["verified", "provenance"]
    writer = csv.writer(buf)
    writer.writerow(columns)

    def _safe_cell(val: str) -> str:
        text = str(val or "")
        if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + text
        return text

    for row in artifact.table_rows:
        prov = "; ".join(f"{c.document_id}#{c.chunk_index}" for c in row.citations) or "unverified"
        values = [_safe_cell(row.cells.get(col, "")) for col in artifact.table_columns]
        values.append("verified" if row.verified else "unverified")
        values.append(_safe_cell(prov))
        writer.writerow(values)
    return buf.getvalue()

