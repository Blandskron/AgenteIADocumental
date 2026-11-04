from docx import Document as DocxDocument

from app.shared.utils import normalize_text


class DocxExtractor:
    supported_mime_types = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    def extract(self, file_path: str) -> str:
        document = DocxDocument(file_path)
        blocks: list[str] = []
        blocks.extend(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        return normalize_text("\n".join(blocks))
