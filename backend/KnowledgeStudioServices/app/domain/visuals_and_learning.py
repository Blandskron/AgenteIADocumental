"""Knowledge Studio P1 — Visualizaciones deterministas (R5-03) y Quizzes/Flashcards con SM-2 offline (R5-04)."""

from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import BaseModel, Field

from app.domain.artifacts import ArtifactContent, Citation, _norm

FORBIDDEN_DIAGRAM_PATTERNS = (
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"foreignobject", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"click\s+\w+\s+href", re.IGNORECASE),
)


class QuizQuestion(BaseModel):
    prompt: str = Field(min_length=5, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)
    explanation: str = Field(min_length=5, max_length=600)
    citations: list[Citation] = Field(min_length=1)


class FlashcardState(BaseModel):
    card_id: str
    front: str
    back: str
    repetitions: int = 0
    interval_days: int = 1
    ease_factor: float = 2.5


@dataclass(frozen=True)
class ChartSeriesPoint:
    label: str
    value: float
    provenance: str


def sanitize_mermaid_diagram(source: str) -> str:
    """Validates Mermaid source for strict client-side rendering (no scripts, foreignObject, or external URLs)."""
    text = (source or "").strip()
    if not text:
        raise ValueError("Empty Mermaid diagram.")
    for pattern in FORBIDDEN_DIAGRAM_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"Unsafe directive rejected in Mermaid diagram: {pattern.pattern}")
    return text


def build_concept_graph_from_wikilinks(documents: list[dict]) -> dict:
    """Builds a deterministic concept map (nodes & edges) from Markdown wikilinks without LLM hallucination."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    for doc in documents:
        doc_id = str(doc.get("document_id") or doc.get("id") or "")
        label = str(doc.get("title") or doc.get("filename") or doc_id)
        if doc_id and doc_id not in seen_nodes:
            seen_nodes.add(doc_id)
            nodes.append({"id": doc_id, "label": label})
        for link in doc.get("wikilinks") or []:
            target_id = f"ref:{link}"
            if target_id not in seen_nodes:
                seen_nodes.add(target_id)
                nodes.append({"id": target_id, "label": str(link)})
            if doc_id:
                edges.append({"source": doc_id, "target": target_id})
    return {"nodes": nodes, "edges": edges}


def extract_verified_chart_series(
    artifact: ArtifactContent,
    label_column: str,
    value_column: str,
) -> list[ChartSeriesPoint]:
    """Generates numeric chart points strictly from verified evidence_table cells — zero invented values."""
    points: list[ChartSeriesPoint] = []
    for row in artifact.table_rows:
        if not row.verified or not row.citations:
            continue
        raw_val = str(row.cells.get(value_column, "")).replace(",", "").strip()
        try:
            numeric = float(raw_val)
        except ValueError:
            continue
        label = str(row.cells.get(label_column, "")).strip()
        prov = "; ".join(f"{c.document_id}#{c.chunk_index}" for c in row.citations)
        points.append(ChartSeriesPoint(label=label, value=numeric, provenance=prov))
    return points


def filter_valid_quiz_questions(
    questions: list[QuizQuestion],
    chunk_lookup: dict[tuple[str, int], str],
) -> list[QuizQuestion]:
    """Keeps only questions with a valid single correct option and anchored source citation."""
    valid: list[QuizQuestion] = []
    for q in questions:
        if q.correct_index >= len(q.options):
            continue
        if len({opt.strip().lower() for opt in q.options}) != len(q.options):
            continue
        anchored = any(
            (chunk := chunk_lookup.get((c.document_id, c.chunk_index))) is not None
            and _norm(c.quote_text) in _norm(chunk)
            for c in q.citations
        )
        if anchored:
            valid.append(q)
    return valid


def sm2_review(card: FlashcardState, quality: int) -> FlashcardState:
    """Pure offline SM-2 spaced-repetition update (quality 0..5, zero telemetry)."""
    q = max(0, min(5, int(quality)))
    if q < 3:
        return card.model_copy(update={"repetitions": 0, "interval_days": 1})
    reps = card.repetitions + 1
    if reps == 1:
        interval = 1
    elif reps == 2:
        interval = 6
    else:
        interval = max(1, round(card.interval_days * card.ease_factor))
    ef = max(1.3, card.ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    return card.model_copy(update={"repetitions": reps, "interval_days": interval, "ease_factor": round(ef, 4)})

