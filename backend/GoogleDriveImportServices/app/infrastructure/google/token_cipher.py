import base64
import hashlib

from cryptography.fernet import Fernet


class TokenCipher:
    def __init__(self, secret: str) -> None:
        if len(secret) < 32 or secret.lower().startswith(("change", "local-", "example")):
            raise ValueError("Drive encryption secret is unavailable.")
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
