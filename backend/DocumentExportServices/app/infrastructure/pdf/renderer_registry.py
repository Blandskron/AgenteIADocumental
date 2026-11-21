"""Registry of DocumentExportServices renderers by `source_type` (R4-04).

Preserves the existing `chat_message` PDF contract untouched while adding
support for `studio_artifact` exports (Markdown/PDF payload preparation).
"""

from collections.abc import Callable
from typing import Any


class RendererRegistry:
    def __init__(self) -> None:
        self._renderers: dict[str, Callable[[dict[str, Any]], bytes]] = {}

    def register(self, source_type: str, renderer: Callable[[dict[str, Any]], bytes]) -> None:
        self._renderers[source_type] = renderer

    def supported_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._renderers))

    def render(self, source_type: str, payload: dict[str, Any]) -> bytes:
        renderer = self._renderers.get(source_type)
        if renderer is None:
            raise ValueError(f"Unsupported export source_type: {source_type}")
        return renderer(payload)


def render_studio_artifact_markdown(payload: dict[str, Any]) -> bytes:
    """Renders a verified Knowledge Studio artifact snapshot to UTF-8 Markdown with explicit provenance."""
    title = str(payload.get("title") or "Artefacto Knowledge Studio").strip()
    template_id = str(payload.get("template_id") or "unknown").strip()
    body_md = str(payload.get("body_md") or "").strip()
    gaps = payload.get("gaps") or []
    sources = payload.get("sources") or []

    lines = [f"# {title}", "", f"_Plantilla:_ `{template_id}`", ""]
    if body_md:
        lines.extend([body_md, ""])
    if gaps:
        lines.append("## Vacíos de información (sin fuente)")
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("")
    if sources:
        lines.append("## Fuentes verificadas")
        for idx, src in enumerate(sources, start=1):
            doc_id = src.get("document_id", "desconocido")
            chunk_idx = src.get("chunk_index", 0)
            lines.append(f"{idx}. `{doc_id}` (fragmento #{chunk_idx})")
        lines.append("")
    return ("\n".join(lines).strip() + "\n").encode("utf-8")


def build_default_registry(chat_pdf_renderer: Callable[[dict[str, Any]], bytes] | None = None) -> RendererRegistry:
    registry = RendererRegistry()
    if chat_pdf_renderer is not None:
        registry.register("chat_message", chat_pdf_renderer)
    registry.register("studio_artifact", render_studio_artifact_markdown)
    return registry

