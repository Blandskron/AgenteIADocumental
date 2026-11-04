from zipfile import BadZipFile, ZipFile

from docx import Document as DocxDocument

from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text


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
        blocks.extend(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        return normalize_text("\n".join(blocks))
