import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.shared.constants import MAX_DOCUMENT_BYTES
from app.shared.errors import PayloadTooLarge


class LocalDocumentStorage:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, source: BinaryIO) -> tuple[str, int]:
        safe_name = self._sanitize_filename(filename)
        storage_path = f"{uuid4().hex}_{safe_name}"
        destination = self._base_path / storage_path

        size = 0
        output = destination.open("xb")
        try:
            with output:
                while chunk := source.read(64 * 1024):
                    size += len(chunk)
                    if size > MAX_DOCUMENT_BYTES:
                        raise PayloadTooLarge("Document exceeds 20 MiB.")
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return storage_path, size

    def remove(self, storage_path: str) -> None:
        (self._base_path / storage_path).unlink(missing_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name.strip() or "document"
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)
