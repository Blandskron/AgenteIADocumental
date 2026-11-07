import json
import math


TEXT_FIELDS = {"full_name": 120, "location": 120, "position": 120, "department": 120,
               "bio": 2000, "preferred_language": 16}


def validate_metadata(value):
    if value is None:
        return None
    nodes, pending = 0, [(value, 0)]
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 4 or nodes > 256:
            raise ValueError("Metadata exceeds structural limits.")
        if isinstance(item, dict):
            if len(item) > 64:
                raise ValueError("Too many metadata keys.")
            for key, child in item.items():
                if not isinstance(key, str) or not 1 <= len(key) <= 64 or any(ord(c) < 32 for c in key):
                    raise ValueError("Invalid metadata key.")
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > 256:
                raise ValueError("Too many metadata entries.")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            if len(item) > 2048 or "\x00" in item:
                raise ValueError("Metadata string exceeds limits.")
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError("Metadata must contain JSON values.")
        elif type(item) is float and not math.isfinite(item):
            raise ValueError("Metadata numbers must be finite.")
    for name, limit in TEXT_FIELDS.items():
        if name in value and (type(value[name]) is not str or len(value[name]) > limit):
            raise ValueError("Invalid presentation field.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid metadata encoding.") from None
    if len(encoded) > 16384:
        raise ValueError("Metadata exceeds 16384 bytes.")
    return value
