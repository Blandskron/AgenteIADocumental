from pathlib import Path
from urllib.parse import urlparse

from app.shared.errors import ValidationError


class LocalDocumentPathResolver:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()

    def resolve(self, storage_path: str) -> Path:
        parsed = urlparse(storage_path)
        if parsed.scheme and parsed.scheme != "file":
            raise ValidationError(f"Unsupported storage scheme: {parsed.scheme}")

        raw_path = Path(parsed.path if parsed.scheme == "file" else storage_path)
        candidate = raw_path if raw_path.is_absolute() else self._base_path / raw_path
        resolved = candidate.resolve()

        if not self._is_inside_base_path(resolved):
            raise ValidationError("Document path is outside the configured storage directory.")
        if not resolved.exists():
            raise FileNotFoundError(f"Document file not found: {resolved}")
        if not resolved.is_file():
            raise ValidationError(f"Document path is not a file: {resolved}")

        return resolved

    def _is_inside_base_path(self, path: Path) -> bool:
        return path == self._base_path or self._base_path in path.parents
