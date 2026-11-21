import base64
import hashlib
import json
import os
import re

from cryptography.fernet import Fernet, InvalidToken


KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WEAK_PREFIXES = ("change", "local-", "example", "django-insecure-", "synthetic-example")
ENVELOPE_PREFIX = "secrets1"
MAX_KEYS = 4


class SecretDecryptionError(ValueError):
    """Raised when an encrypted secret cannot be decrypted with the configured keyring."""


def _validate_key_material(key_id: str, secret: str) -> None:
    if not isinstance(key_id, str) or not KEY_ID_PATTERN.fullmatch(key_id):
        raise ValueError("Invalid secrets encryption key identifier.")
    if (
        not isinstance(secret, str)
        or len(secret) < 32
        or len(set(secret)) < 5
        or secret.lower().startswith(WEAK_PREFIXES)
    ):
        raise ValueError("Secrets encryption key is missing or too weak.")


class SecretsCipher:
    """Authenticated encryption at rest (`secrets1.<key_id>.<fernet>`) with key rotation."""

    def __init__(
        self,
        secret: str,
        key_id: str = "v1",
        previous: dict[str, str] | None = None,
    ) -> None:
        previous_map = dict(previous or {})
        if key_id in previous_map:
            raise ValueError("Active secrets key_id must not appear in previous keys.")
        keys = {**previous_map, key_id: secret}
        if len(keys) > MAX_KEYS:
            raise ValueError(f"At most {MAX_KEYS} encryption keys are supported.")
        for identifier, value in keys.items():
            _validate_key_material(identifier, value)
        self.key_id = key_id
        self._keys = {
            name: Fernet(base64.urlsafe_b64encode(hashlib.sha256(value.encode("utf-8")).digest()))
            for name, value in keys.items()
        }

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        token = self._keys[self.key_id].encrypt(value.encode("utf-8")).decode("ascii")
        return f"{ENVELOPE_PREFIX}.{self.key_id}.{token}"

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            if not isinstance(value, str) or not value.startswith(f"{ENVELOPE_PREFIX}."):
                raise ValueError("Unsupported secret envelope.")
            _, identifier, ciphertext = value.split(".", 2)
            return self._keys[identifier].decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, KeyError, ValueError, UnicodeError, AttributeError):
            raise SecretDecryptionError(
                "Encrypted integration credentials cannot be decrypted with the current keyring."
            ) from None

    @staticmethod
    def fingerprint(secret_value: str) -> str:
        """Short non-reversible fingerprint (last 4 hex chars of SHA-256, never the raw key)."""
        return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()[-4:]

    @classmethod
    def from_environ(cls, environ: dict[str, str] | None = None) -> "SecretsCipher | None":
        env = os.environ if environ is None else environ
        raw_secret = env.get("SECRETS_ENCRYPTION_KEY", "")
        if not raw_secret:
            return None
        key_id = env.get("SECRETS_KEY_ID", "v1").strip() or "v1"
        raw_previous = env.get("SECRETS_PREVIOUS_KEYS", "").strip()
        previous: dict[str, str] = {}
        if raw_previous:
            parsed = json.loads(raw_previous)
            if not isinstance(parsed, dict):
                raise ValueError("SECRETS_PREVIOUS_KEYS must be a JSON object.")
            previous = parsed
        return cls(raw_secret, key_id=key_id, previous=previous)

