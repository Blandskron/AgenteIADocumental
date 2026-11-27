from zipfile import BadZipFile, ZipFile

from docx import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text


def _render_docx_table_markdown(table: Table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [cell.text.replace("\n", " ").replace("|", "\\|").strip() for cell in row.cells]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    padded = [r + [""] * (col_count - len(r)) for r in rows]
    header = "| " + " | ".join(padded[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
    body = ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join([header, sep, *body])


class DocxExtractor:
    supported_mime_types = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    def extract(self, file_path: str) -> str:
        try:
            with ZipFile(file_path) as archive:
                entries = archive.infolist()
                if len(entries) > 1024 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
                    raise ExtractionError("DOCX exceeds the archive expansion limit.")
        except BadZipFile as exc:
            raise ExtractionError("Invalid DOCX archive.") from exc
        document = DocxDocument(file_path)
        blocks: list[str] = []
        body = document.element.body
        for child in body.iterchildren():
            if isinstance(child, CT_P):
                paragraph = Paragraph(child, document)
                content = paragraph.text.strip()
                if not content:
                    continue
                style_name = (paragraph.style.name or "").strip().lower() if paragraph.style else ""
                if style_name.startswith("heading"):
                    level_digits = "".join(ch for ch in style_name if ch.isdigit())
                    level = min(6, max(1, int(level_digits))) if level_digits else 1
                    blocks.append(f"{'#' * level} {content}")
                else:
                    blocks.append(content)
            elif isinstance(child, CT_Tbl):
                table = Table(child, document)
                table_md = _render_docx_table_markdown(table)
                if table_md:
                    blocks.append(table_md)
        return normalize_text("\n\n".join(blocks))
