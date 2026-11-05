from pathlib import Path
from stat import S_ISLNK, S_ISREG
from urllib.parse import urlparse
from urllib.request import url2pathname

from app.shared.errors import ValidationError


class LocalDocumentPathResolver:
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path).resolve()

    def resolve(self, storage_path: str) -> Path:
        candidate = self._candidate(storage_path)
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError("Document path is unavailable.") from exc
        if not self._is_inside_base_path(resolved):
            raise ValidationError("Document path is outside the configured storage directory.")
        try:
            mode = resolved.stat().st_mode
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise ValidationError("Document path is unavailable.") from exc
        if not S_ISREG(mode):
            raise ValidationError("Document path is not a file.")
        return resolved

    def resolve_for_deletion(self, storage_path: str) -> Path:
        candidate = self._candidate(storage_path)
        try:
            parent = candidate.parent.resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError("Document path is unavailable.") from exc
        if candidate.name in ("", ".", "..") or not self._is_inside_base_path(parent):
            raise ValidationError("Document path is outside the configured storage directory.")
        entry = parent / candidate.name
        try:
            mode = entry.lstat().st_mode
        except FileNotFoundError:
            return entry
        if not (S_ISREG(mode) or S_ISLNK(mode)):
            raise ValidationError("Document path is not a file.")
        return entry

    def _candidate(self, storage_path: str) -> Path:
        if not storage_path or any(ord(character) < 32 or ord(character) == 127 for character in storage_path):
            raise ValidationError("Invalid document path.")
        raw_path = Path(storage_path)
        if not raw_path.is_absolute():
            try:
                parsed = urlparse(storage_path)
            except ValueError as exc:
                raise ValidationError("Invalid document URI.") from exc
            if parsed.scheme:
                if parsed.scheme != "file" or parsed.netloc.lower() not in ("", "localhost"):
                    raise ValidationError("Unsupported document location.")
                if parsed.query or parsed.fragment:
                    raise ValidationError("Invalid document URI.")
                decoded_path = url2pathname(parsed.path)
                if any(ord(character) < 32 or ord(character) == 127 for character in decoded_path):
                    raise ValidationError("Invalid document URI.")
                raw_path = Path(decoded_path)
                if not raw_path.is_absolute():
                    raise ValidationError("Document URI must be absolute.")
        return raw_path if raw_path.is_absolute() else self._base_path / raw_path

    def _is_inside_base_path(self, path: Path) -> bool:
        return path == self._base_path or self._base_path in path.parents
