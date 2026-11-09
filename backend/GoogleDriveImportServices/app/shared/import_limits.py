import json
import math
import re

from app.shared.errors import ValidationError

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024
FILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}
RESERVED_METADATA = {
    "source",
    "owner_user_id",
    "user_id",
    "tenant_id",
    "active_tenant_id",
    "import_id",
    "folder_id",
    "google_file_id",
    "google_web_view_link",
    "google_mime_type",
    "operation_id",
}


def validate_metadata(value):
    def visit(item, depth):
        if depth > 4:
            raise ValueError()
        if isinstance(item, dict):
            if len(item) > 32 or any(
                not isinstance(key, str) or not 1 <= len(key) <= 64 for key in item
            ):
                raise ValueError()
            for nested in item.values():
                visit(nested, depth + 1)
        elif isinstance(item, list):
            if len(item) > 32:
                raise ValueError()
            for nested in item:
                visit(nested, depth + 1)
        elif isinstance(item, str):
            if len(item) > 512 or any(ord(char) < 32 for char in item):
                raise ValueError()
        elif item is not None and (
            type(item) not in (int, float, bool) or not math.isfinite(item)
        ):
            raise ValueError()

    try:
        if not isinstance(value, dict) or RESERVED_METADATA.intersection(value):
            raise ValueError()
        visit(value, 0)
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 4096:
            raise ValueError()
    except (ValueError, OverflowError, TypeError, RecursionError):
        raise ValueError(
            "Import metadata exceeds supported limits or contains reserved fields."
        ) from None
    return value


def safe_filename(value, mime_type):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or value in {".", ".."}
        or any(ord(char) < 32 or char in "/\\\x7f" for char in value)
    ):
        raise ValidationError("Unsupported Google Drive filename.")
    extension = MIME_EXTENSIONS[mime_type]
    accepted = (
        {extension, ".jpeg"}
        if mime_type == "image/jpeg"
        else {extension, ".tif"}
        if mime_type == "image/tiff"
        else {extension}
    )
    stem = value.rsplit(".", 1)[0] if "." in value else value
    return (
        value
        if any(value.lower().endswith(suffix) for suffix in accepted)
        else stem[:180] + extension
    )
