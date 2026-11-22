"""Deterministic multi-document contract clause comparator with [Fuente N] anchoring (AG-026)."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from app.application.templates.agent_templates import ISO_DATE_RE, LATAM_DATE_RE, MONEY_RE

CLAUSE_CATEGORIES: dict[str, re.Pattern[str]] = {
    "penalizacion": re.compile(r"\b(penalizaci[oó]n|multa|recargo|mora|incumplimiento)\b", re.IGNORECASE),
    "vigencia_vencimiento": re.compile(r"\b(vigencia|vencimiento|plazo|renovaci[oó]n|expira)\b", re.IGNORECASE),
    "monto_pago": re.compile(r"\b(monto|importe|tarifa|precio|honorario|pago|factura)\b", re.IGNORECASE),
    "rescision": re.compile(r"\b(rescisi[oó]n|terminaci[oó]n|preaviso|cancelaci[oó]n)\b", re.IGNORECASE),
    "confidencialidad": re.compile(r"\b(confidencial|secreto|nda|privacidad|datos personales)\b", re.IGNORECASE),
}


def compare_contract_clauses(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Groups verified evidence by document_id, detects clause categories and renders a comparison table."""
    by_doc: dict[str, dict[str, Any]] = {}
    for idx, src in enumerate(sources, start=1):
        doc_id = str(src.get("document_id") or f"doc-{idx}")
        filename = str(src.get("filename") or doc_id)
        quote = str(src.get("quote") or "")
        source_index = int(src.get("source_index") or idx)

        entry = by_doc.setdefault(
            doc_id,
            {
                "document_id": doc_id,
                "filename": filename,
                "clauses": defaultdict(list),
                "dates": [],
                "amounts": [],
                "source_indices": [],
            },
        )
        if source_index not in entry["source_indices"]:
            entry["source_indices"].append(source_index)

        for cat_name, pattern in CLAUSE_CATEGORIES.items():
            if pattern.search(quote):
                entry["clauses"][cat_name].append(
                    {"source_index": source_index, "quote": quote[:180]}
                )

        for d in list(ISO_DATE_RE.findall(quote)) + list(LATAM_DATE_RE.findall(quote)):
            if d not in entry["dates"]:
                entry["dates"].append(d)
        for m in MONEY_RE.findall(quote):
            cleaned = m.strip()
            if cleaned not in entry["amounts"]:
                entry["amounts"].append(cleaned)

    docs = list(by_doc.values())
    differences: list[dict[str, Any]] = []
    if len(docs) >= 2:
        for cat_name in CLAUSE_CATEGORIES:
            present_in = [d["filename"] for d in docs if d["clauses"].get(cat_name)]
            missing_in = [d["filename"] for d in docs if not d["clauses"].get(cat_name)]
            if present_in and missing_in:
                differences.append(
                    {
                        "category": cat_name,
                        "present_in": present_in,
                        "missing_in": missing_in,
                    }
                )

    # Render compact Markdown comparison table
    md_lines = [
        "| Documento | Fechas | Montos / % | Cláusulas detectadas | Fuentes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for doc in docs:
        dates_str = ", ".join(doc["dates"]) or "—"
        amounts_str = ", ".join(doc["amounts"]) or "—"
        cats_str = ", ".join(sorted(doc["clauses"].keys())) or "—"
        refs_str = " ".join(f"[Fuente {i}]" for i in doc["source_indices"])
        md_lines.append(f"| {doc['filename']} | {dates_str} | {amounts_str} | {cats_str} | {refs_str} |")

    serialized_docs = [
        {
            "document_id": d["document_id"],
            "filename": d["filename"],
            "clauses": dict(d["clauses"]),
            "dates": d["dates"],
            "amounts": d["amounts"],
            "source_indices": d["source_indices"],
        }
        for d in docs
    ]
    return {
        "documents_compared": len(serialized_docs),
        "documents": serialized_docs,
        "differences": differences,
        "comparison_markdown": "\n".join(md_lines),
    }
