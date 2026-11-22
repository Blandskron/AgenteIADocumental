"""Curated, policy-validated Code Mode transformation presets (AG-041)."""

from __future__ import annotations

from typing import Any

from app.infrastructure.sandbox.sandbox_client import validate_sandbox_script

CODE_MODE_PRESETS: dict[str, dict[str, str]] = {
    "group_by_document": {
        "preset_id": "group_by_document",
        "title": "Agrupar fragmentos por documento",
        "description": "Agrupa toda la evidencia recuperada por document_id y cuenta fragmentos por archivo.",
        "code": (
            "function transform(data: { evidence: Array<{ document_id: string; filename: string }> }) {\n"
            "  const grouped: Record<string, { filename: string; chunks: number }> = {};\n"
            "  for (const item of data.evidence || []) {\n"
            "    const key = item.document_id || 'unknown';\n"
            "    if (!grouped[key]) grouped[key] = { filename: item.filename || key, chunks: 0 };\n"
            "    grouped[key].chunks += 1;\n"
            "  }\n"
            "  return grouped;\n"
            "}"
        ),
    },
    "sum_numeric_amounts": {
        "preset_id": "sum_numeric_amounts",
        "title": "Sumar importes detectados",
        "description": "Extrae valores monetarios (USD/$/EUR) de la evidencia recuperada y calcula el total.",
        "code": (
            "function transform(data: { evidence: Array<{ document_id: string; quote: string }> }) {\n"
            "  const re = /(?:USD|EUR|\\$)\\s?(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{1,2})?|\\d+(?:\\.\\d{1,2})?)/gi;\n"
            "  let total = 0;\n"
            "  const items: Array<{ document_id: string; amount: number }> = [];\n"
            "  for (const row of data.evidence || []) {\n"
            "    for (const m of (row.quote || '').matchAll(re)) {\n"
            "      const val = Number(m[1].replace(/,/g, ''));\n"
            "      if (Number.isFinite(val)) { total += val; items.push({ document_id: row.document_id, amount: val }); }\n"
            "    }\n"
            "  }\n"
            "  return { total: Number(total.toFixed(2)), count: items.length, items };\n"
            "}"
        ),
    },
    "filter_iso_dates": {
        "preset_id": "filter_iso_dates",
        "title": "Ordenar fechas cronológicamente",
        "description": "Extrae fechas YYYY-MM-DD de la evidencia y las ordena cronológicamente.",
        "code": (
            "function transform(data: { evidence: Array<{ document_id: string; quote: string }> }) {\n"
            "  const re = /\\b(20\\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\\d|3[01]))\\b/g;\n"
            "  const found: Array<{ date: string; document_id: string }> = [];\n"
            "  for (const row of data.evidence || []) {\n"
            "    for (const m of (row.quote || '').matchAll(re)) {\n"
            "      found.push({ date: m[1], document_id: row.document_id });\n"
            "    }\n"
            "  }\n"
            "  found.sort((a, b) => a.date.localeCompare(b.date));\n"
            "  return { count: found.length, timeline: found };\n"
            "}"
        ),
    },
}


def list_code_mode_presets() -> list[dict[str, Any]]:
    """Returns all curated presets after verifying each passes static sandbox policy."""
    items = []
    for preset in CODE_MODE_PRESETS.values():
        validate_sandbox_script(preset["code"])
        items.append(dict(preset))
    return items
