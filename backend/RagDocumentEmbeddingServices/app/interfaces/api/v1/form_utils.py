import json
import mimetypes

from fastapi import UploadFile

from app.shared.errors import ValidationError


def parse_metadata(metadata: str | None) -> dict:
    if not metadata:
        return {}
    try:
        payload = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise ValidationError("metadata must be a valid JSON object.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("metadata must be a valid JSON object.")
    return payload


def detect_mime_type(file: UploadFile) -> str:
    return file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
