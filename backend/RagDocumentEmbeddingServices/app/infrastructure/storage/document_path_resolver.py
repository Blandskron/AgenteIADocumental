from pathlib import Path
from urllib.parse import urlparse

from app.shared.errors import ValidationError


class LocalDocumentPathResolver:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()

    def resolve(self, storage_path: str) -> str:
        raw_path = Path(storage_path)
        if raw_path.is_absolute():
            return self._validate_file(raw_path)

        parsed = urlparse(storage_path)
        if parsed.scheme and parsed.scheme not in {"file"}:
            raise ValidationError(f"Unsupported remote storage scheme: {parsed.scheme}")

        candidate = Path(parsed.path if parsed.scheme == "file" else storage_path)
        if not candidate.is_absolute():
            candidate = self._base_path / candidate

        return self._validate_file(candidate)

    def _validate_file(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Document file not found: {resolved}")
        if not resolved.is_file():
            raise ValidationError(f"Document path is not a file: {resolved}")
        return str(resolved)
