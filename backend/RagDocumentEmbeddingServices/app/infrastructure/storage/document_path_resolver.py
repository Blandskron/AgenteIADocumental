from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from app.shared.errors import ValidationError


class LocalDocumentPathResolver:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()

    def resolve(self, storage_path: str) -> str:
        candidate = Path(storage_path)
        if not candidate.is_absolute():
            parsed = urlparse(storage_path)
            if parsed.scheme == "file" and parsed.netloc in ("", "localhost"):
                candidate = Path(url2pathname(parsed.path))
            elif parsed.scheme or parsed.netloc:
                raise ValidationError("Unsupported document storage URL.")

        try:
            resolved = (self._base_path / candidate).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError("Invalid document storage path.") from exc
        if not resolved.is_relative_to(self._base_path):
            raise ValidationError("Document path is outside the storage directory.")
        if not resolved.is_file():
            raise ValidationError("Document file does not exist in storage.")
        return str(resolved)
