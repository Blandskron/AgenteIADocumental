import base64
import json
import re
from datetime import UTC, datetime

from app.shared.errors import ValidationError


def encode_cursor(row, owner, source_type):
    data = {"v": 1, "at": row.created_at.isoformat(), "id": row.export_id, "owner": owner, "source": source_type}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_cursor(value, owner, source_type):
    try:
        if len(value) > 512:
            raise ValueError
        data = json.loads(base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True))
        if (type(data) is not dict or set(data) != {"v", "at", "id", "owner", "source"}
                or type(data["v"]) is not int or data["v"] != 1 or data["owner"] != owner
                or data["source"] != source_type or not isinstance(data["id"], str)
                or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", data["id"]) is None or not isinstance(data["at"], str)):
            raise ValueError
        created = datetime.fromisoformat(data["at"])
        if created.tzinfo is None:
            raise ValueError
        return created.astimezone(UTC), data["id"]
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValidationError("Invalid export cursor.") from None
