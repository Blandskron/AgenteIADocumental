import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from app.shared.errors import ReauthorizationRequired


class TokenCipher:
    def __init__(self, secret, key_id="v1", previous=None, legacy_key_id=None):
        keys = {**(previous or {}), key_id: secret}
        if len(keys) > 4 or key_id in (previous or {}):
            raise ValueError("Invalid Drive encryption key configuration.")
        for identifier, value in keys.items():
            if (not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", identifier) or not isinstance(value, str)
                    or len(value) < 32 or value.lower().startswith(("change", "local-", "example"))):
                raise ValueError("Drive encryption secret is unavailable.")
        if legacy_key_id is not None and legacy_key_id not in keys:
            raise ValueError("Legacy Drive key is unavailable.")
        self.key_id, self.legacy_key_id = key_id, legacy_key_id
        self._keys = {name: Fernet(base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()))
                      for name, value in keys.items()}

    def encrypt(self, value):
        if value is None:
            return None
        return "drive1." + self.key_id + "." + self._keys[self.key_id].encrypt(value.encode()).decode()

    def decrypt(self, value):
        if value is None:
            return None
        try:
            if value.startswith("drive1."):
                _, identifier, ciphertext = value.split(".", 2)
            elif self.legacy_key_id:
                identifier, ciphertext = self.legacy_key_id, value
            else:
                raise ValueError()
            return self._keys[identifier].decrypt(ciphertext.encode()).decode()
        except (InvalidToken, KeyError, ValueError, UnicodeError, AttributeError):
            raise ReauthorizationRequired("Drive credentials require reviewed migration or authorization.") from None

    @classmethod
    def from_settings(cls, settings):
        return cls(settings.google_token_encryption_key, settings.google_token_key_id,
                   settings.google_token_previous_keys, settings.google_token_legacy_key_id or None)
