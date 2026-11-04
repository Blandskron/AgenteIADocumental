import re
import shutil
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


class LocalDocumentStorage:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, source: BinaryIO) -> tuple[str, int]:
        safe_name = self._sanitize_filename(filename)
        storage_path = f"{uuid4().hex}_{safe_name}"
        destination = self._base_path / storage_path

        with destination.open("wb") as output:
            shutil.copyfileobj(source, output)

        return storage_path, destination.stat().st_size

    def _sanitize_filename(self, filename: str) -> str:
        name = Path(filename).name.strip() or "document"
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)
