import json
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from threading import Lock

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config.export_limits import MAX_PAGES, MAX_PDF
from app.shared.errors import ExportGenerationError, ExportLimitError, ValidationError

FONT_LOCK = Lock()


def register_fonts():
    with FONT_LOCK:
        if "NotoSans" not in pdfmetrics.getRegisteredFontNames():
            base = Path(__file__).parent / "fonts"
            for name, file in [("NotoSans", "NotoSans-Regular.ttf"), ("NotoSansBold", "NotoSans-Bold.ttf")]:
                pdfmetrics.registerFont(TTFont(name, str(base / file)))


class BoundedBuffer(BytesIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_PDF:
            raise ExportLimitError("PDF exceeds output limit.")
        return super().write(value)


class ChatPdfRenderer:
    def render(self, export) -> bytes:
        register_fonts()
        output = BoundedBuffer()
        def page(canvas, doc):
            if doc.page > MAX_PAGES:
                raise ExportLimitError("PDF exceeds page limit.")
            canvas.saveState()
            canvas.setFont("NotoSans", 8)
            canvas.setFillColor(colors.HexColor("#667085"))
            canvas.drawString(18 * mm, 12 * mm, "Blandskron Documental")
            canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))
            canvas.restoreState()
        try:
            doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                                    topMargin=18*mm, bottomMargin=20*mm, title=export.title, author="Blandskron Documental")
            doc.build(self._story(export), onFirstPage=page, onLaterPages=page)
            return output.getvalue()
        except ValidationError:
            raise
        except Exception:
            raise ExportGenerationError("PDF generation failed.") from None

    def _story(self, export):
        title = ParagraphStyle("title", fontName="NotoSansBold", fontSize=18, leading=23, spaceAfter=10)
        heading = ParagraphStyle("heading", fontName="NotoSansBold", fontSize=11, leading=15,
                                 spaceBefore=12, spaceAfter=6, keepWithNext=True)
        body = ParagraphStyle("body", fontName="NotoSans", fontSize=10, leading=14, spaceAfter=6,
                              splitLongWords=True, allowWidows=0, allowOrphans=0)
        small = ParagraphStyle("small", parent=body, fontSize=8, leading=11)
        table_heading = ParagraphStyle("table-heading", parent=heading, keepWithNext=False)
        table_header = ParagraphStyle("table-header", parent=small, fontName="NotoSansBold")
        def paragraph(text, style=body):
            return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)
        story = [paragraph(export.title, title), paragraph(datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"), small),
                 paragraph("Pregunta", heading), paragraph(export.question or "Sin pregunta."),
                 paragraph("Respuesta", heading)]
        # Plain text (including literal Markdown), with bounded paragraphs; no user markup is parsed.
        for line in export.answer.split("\n"):
            story.append(paragraph(line or " "))
        if export.sources:
            rows = [[paragraph(name, table_header) for name in ["Documento", "Página", "Fragmento"]]]
            def cell(value):
                return paragraph(" ".join(str(value).split()), small)
            for source in export.sources:
                rows.append([cell(source.get("filename") or source.get("document_id") or "Documento"),
                             cell(source.get("page") or source.get("page_number") or ""),
                             cell(source.get("snippet") or source.get("content") or source.get("chunk") or "")])
            widths = [45*mm, 15*mm, 114*mm]
            table = Table(rows, colWidths=widths, repeatRows=1, splitByRow=1)
            style = TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eef2f6")),
                                       ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#cbd5e1")),
                                       ("VALIGN", (0,0), (-1,-1), "TOP"),
                                       ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
                                       ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)])
            table.setStyle(style)
            first_rows = Table(rows[:2], colWidths=widths)
            first_rows.setStyle(style)
            required_height = first_rows.wrap(174*mm, 10000)[1] + 40
            story.extend([CondPageBreak(required_height), paragraph("Fuentes aportadas por el cliente", table_heading), table])
        if export.metadata:
            story.extend([paragraph("Metadatos", heading), paragraph(json.dumps(export.metadata, ensure_ascii=False, sort_keys=True), small)])
        story.append(Spacer(1, 4))
        return story
