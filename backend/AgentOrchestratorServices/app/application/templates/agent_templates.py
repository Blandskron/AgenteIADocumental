"""Specialized documentary agent templates & deterministic date/amount extractors (AG-016)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

ISO_DATE_RE = re.compile(r"\b(20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b")
LATAM_DATE_RE = re.compile(r"\b((?:0[1-9]|[12]\d|3[01])/(?:0[1-9]|1[0-2])/20\d{2})\b")
MONEY_RE = re.compile(
    r"(?:(?:USD|US\$|EUR|CLP|MXN|ARS|COP|\$)\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\b\d+(?:[.,]\d{1,2})?\s?%)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentTemplate:
    template_id: str
    title: str
    description: str
    recommended_mode: str  # "agent" | "code_mode"
    default_save_to_studio: bool
    system_instruction: str


AGENT_TEMPLATES: dict[str, AgentTemplate] = {
    "research_general": AgentTemplate(
        template_id="research_general",
        title="Investigación multi-documento",
        description="Investiga entre varios documentos autorizados y sintetiza hallazgos con citas [Fuente N].",
        recommended_mode="agent",
        default_save_to_studio=False,
        system_instruction=(
            "Investiga exhaustivamente en los documentos autorizados, contrasta puntos clave y responde "
            "con una síntesis estructurada citando [Fuente N] en cada afirmación."
        ),
    ),
    "contract_comparison": AgentTemplate(
        template_id="contract_comparison",
        title="Comparación de contratos",
        description="Compara cláusulas, obligaciones, penalizaciones y diferencias entre contratos seleccionados.",
        recommended_mode="code_mode",
        default_save_to_studio=False,
        system_instruction=(
            "Compara cláusula por cláusula los documentos seleccionados (objeto, plazos, penalizaciones, "
            "renovación y rescisión) presentando una tabla Markdown comparativa con citas [Fuente N]."
        ),
    ),
    "dates_amounts_extraction": AgentTemplate(
        template_id="dates_amounts_extraction",
        title="Fechas, montos y vencimientos",
        description="Extrae fechas clave, importes monetarios, porcentajes y alertas de vencimiento.",
        recommended_mode="code_mode",
        default_save_to_studio=False,
        system_instruction=(
            "Extrae todas las fechas, vencimientos, plazos y montos monetarios/porcentuales presentes "
            "en <document_context> en formato tabular verificable, citando [Fuente N] para cada fila."
        ),
    ),
    "executive_report_studio": AgentTemplate(
        template_id="executive_report_studio",
        title="Informe ejecutivo (guardar en Studio)",
        description="Construye un informe citado y solicita aprobación humana antes de guardarlo en Knowledge Studio.",
        recommended_mode="agent",
        default_save_to_studio=True,
        system_instruction=(
            "Redacta un informe ejecutivo con resumen, hallazgos verificados y riesgos detectados "
            "respaldados por citas [Fuente N], listo para aprobación humana y guardado en Knowledge Studio."
        ),
    ),
}


def list_agent_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": tpl.template_id,
            "title": tpl.title,
            "description": tpl.description,
            "recommended_mode": tpl.recommended_mode,
            "default_save_to_studio": tpl.default_save_to_studio,
        }
        for tpl in AGENT_TEMPLATES.values()
    ]


def get_agent_template(template_id: str | None) -> AgentTemplate:
    if not template_id:
        return AGENT_TEMPLATES["research_general"]
    tpl = AGENT_TEMPLATES.get(template_id.strip())
    if tpl is None:
        raise ValueError(f"Plantilla de agente no soportada: {template_id}")
    return tpl


def extract_deterministic_facts(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Deterministic extraction of dates and monetary/percentage amounts anchored to evidence chunks."""
    dates: list[dict[str, Any]] = []
    amounts: list[dict[str, Any]] = []

    for idx, item in enumerate(evidence, start=1):
        quote = str(item.get("quote") or "")
        doc_id = str(item.get("document_id") or "")
        chunk_idx = int(item.get("chunk_index") or 0)
        for match in list(ISO_DATE_RE.findall(quote)) + list(LATAM_DATE_RE.findall(quote)):
            dates.append(
                {"value": match, "source_index": idx, "document_id": doc_id, "chunk_index": chunk_idx}
            )
        for match in MONEY_RE.findall(quote):
            amounts.append(
                {"value": match.strip(), "source_index": idx, "document_id": doc_id, "chunk_index": chunk_idx}
            )
    return {"dates": dates, "amounts": amounts}
