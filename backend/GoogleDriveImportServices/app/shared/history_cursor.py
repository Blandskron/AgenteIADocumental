import base64
import json
import re
from datetime import datetime

from app.shared.errors import ValidationError


def encode_cursor(row, kind, owner, resource=""):
    identifier = row.import_id if kind == "imports" else row.import_file_id
    value = {
        "v": 1,
        "kind": kind,
        "owner": owner,
        "resource": resource,
        "created": row.created_at.isoformat(),
        "id": identifier,
    }
    return (
        base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def decode_cursor(cursor, kind, owner, resource=""):
    if cursor is None:
        return None
    try:
        if not isinstance(cursor, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,1024}", cursor
        ):
            raise ValueError()
        value = json.loads(
            base64.b64decode(
                cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
            )
        )
        if (
            not isinstance(value, dict)
            or set(value) != {"v", "kind", "owner", "resource", "created", "id"}
            or type(value["v"]) is not int
            or value["v"] != 1
            or value["kind"] != kind
            or value["owner"] != owner
            or value["resource"] != resource
            or not isinstance(value["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["id"])
            or not isinstance(value["created"], str)
            or len(value["created"]) > 40
        ):
            raise ValueError()
        created = datetime.fromisoformat(value["created"])
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError()
        return created, value["id"]
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise ValidationError("Invalid Drive history cursor.") from None
