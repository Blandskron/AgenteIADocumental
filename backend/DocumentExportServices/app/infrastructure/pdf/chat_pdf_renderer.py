from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from textwrap import wrap
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.domain.entities import ChatPdfExport
from app.shared.errors import ExportGenerationError


class ChatPdfRenderer:
    def render(self, export: ChatPdfExport, output_path: Path) -> None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=18 * mm,
                rightMargin=18 * mm,
                topMargin=18 * mm,
                bottomMargin=18 * mm,
                title=export.title,
                author="Blandskron Documental",
            )
            doc.build(self._story(export))
        except Exception as exc:
            raise ExportGenerationError(f"No se pudo generar el PDF: {exc}") from exc

    def _story(self, export: ChatPdfExport) -> list:
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "BlandskronTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
            spaceAfter=10,
        )
        section_style = ParagraphStyle(
            "BlandskronSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "BlandskronBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#374151"),
        )
        muted_style = ParagraphStyle(
            "BlandskronMuted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#6b7280"),
        )

        story = [
            Paragraph(self._escape(export.title), title_style),
            Paragraph(f"Exportado por Blandskron Documental el {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", muted_style),
            Spacer(1, 8),
            Paragraph("Pregunta", section_style),
            Paragraph(self._paragraph_text(export.question), body_style),
            Paragraph("Respuesta", section_style),
            Paragraph(self._paragraph_text(export.answer), body_style),
        ]

        if export.sources:
            story.extend([Paragraph("Fuentes", section_style), self._sources_table(export.sources)])

        if export.metadata:
            story.extend([Paragraph("Metadatos", section_style), Paragraph(self._metadata_text(export.metadata), muted_style)])

        return story

    def _sources_table(self, sources: list[dict[str, Any]]) -> Table:
        rows = [["Documento", "Pagina", "Fragmento"]]
        for source in sources:
            rows.append(
                [
                    self._clip(source.get("filename") or source.get("document_id") or "Documento"),
                    str(source.get("page") or source.get("page_number") or ""),
                    self._clip(source.get("snippet") or source.get("content") or source.get("chunk") or "", 90),
                ]
            )
        table = Table(rows, colWidths=[54 * mm, 20 * mm, 84 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _paragraph_text(self, value: str) -> str:
        text = self._escape(value or "")
        return "<br/>".join(text.splitlines()) or "Sin contenido."

    def _metadata_text(self, metadata: dict[str, Any]) -> str:
        lines = [f"{self._escape(str(key))}: {self._escape(str(value))}" for key, value in metadata.items()]
        return "<br/>".join(lines)

    def _clip(self, value: Any, length: int = 56) -> str:
        text = str(value or "").replace("\n", " ").strip()
        if len(text) <= length:
            return self._escape(text)
        return self._escape(" ".join(wrap(text, length)[0:1]) + "...")

    def _escape(self, value: str) -> str:
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

