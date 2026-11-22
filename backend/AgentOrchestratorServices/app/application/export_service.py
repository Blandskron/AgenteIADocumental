"""Direct safe Markdown & CSV export helpers for completed agent runs (AG-020)."""

from __future__ import annotations

import csv
import io
from typing import Any


def _neutralize_csv_formula(value: str) -> str:
    cleaned = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if cleaned and cleaned[0] in ("=", "+", "-", "@", "\t"):
        return "'" + cleaned
    return cleaned


def export_run_markdown(run: dict[str, Any]) -> str:
    """Renders a self-contained Markdown report with verified [Fuente N] appendix."""
    lines = [
        f"# Informe Agente Documental — {run.get('run_id', '')}",
        "",
        f"- **Objetivo:** {run.get('goal', '')}",
        f"- **Estado:** {run.get('status', '')}",
        f"- **Proveedor IA:** {run.get('provider') or 'N/A'}",
        f"- **Pasos:** {run.get('steps_used', 0)} · **Tokens:** {run.get('usage_tokens', 0)}",
        "",
        "## Resultado",
        "",
        str(run.get("result_markdown") or "(Sin contenido generado)"),
        "",
        "## Fuentes verificadas",
        "",
    ]
    sources = run.get("sources") or []
    if not sources:
        lines.append("- Sin fuentes registradas.")
    else:
        for idx, src in enumerate(sources, start=1):
            doc_id = src.get("document_id", "")
            chunk_idx = src.get("chunk_index", 0)
            filename = src.get("filename") or doc_id
            quote = str(src.get("quote") or "").replace("\n", " ").strip()
            lines.append(f"- **[Fuente {idx}]** `{filename}` (`{doc_id}#{chunk_idx}`): {quote}")
    return "\n".join(lines) + "\n"


def export_run_csv(run: dict[str, Any]) -> str:
    """Renders a formula-safe CSV table of verified sources from an agent run."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["run_id", "source_index", "document_id", "chunk_index", "filename", "quote"])
    run_id = str(run.get("run_id") or "")
    for idx, src in enumerate(run.get("sources") or [], start=1):
        writer.writerow(
            [
                _neutralize_csv_formula(run_id),
                idx,
                _neutralize_csv_formula(str(src.get("document_id") or "")),
                int(src.get("chunk_index") or 0),
                _neutralize_csv_formula(str(src.get("filename") or "")),
                _neutralize_csv_formula(str(src.get("quote") or "")),
            ]
        )
    return buf.getvalue()
