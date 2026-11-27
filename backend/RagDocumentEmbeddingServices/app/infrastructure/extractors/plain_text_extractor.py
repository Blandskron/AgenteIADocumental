import csv
import io
from pathlib import Path

from app.shared.utils import normalize_text

MAX_CSV_ROWS = 5000


def _csv_to_markdown(raw_text: str) -> str:
    sample = raw_text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
    rows: list[list[str]] = []
    for row in reader:
        cleaned = [cell.replace("\n", " ").replace("|", "\\|").strip() for cell in row]
        if any(cleaned):
            rows.append(cleaned)
        if len(rows) >= MAX_CSV_ROWS:
            break
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    padded = [r + [""] * (col_count - len(r)) for r in rows]
    header = "| " + " | ".join(padded[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
    body = ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join([header, sep, *body])


class PlainTextExtractor:
    supported_mime_types = {"text/plain", "text/csv"}

    def extract(self, file_path: str) -> str:
        path = Path(file_path)
        raw_text = None
        for encoding in ("utf-8", "latin-1"):
            try:
                raw_text = path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if raw_text is None:
            raw_text = path.read_text(errors="ignore")
        if path.suffix.lower() == ".csv":
            md = _csv_to_markdown(raw_text)
            if md:
                return normalize_text(md)
        return normalize_text(raw_text)
