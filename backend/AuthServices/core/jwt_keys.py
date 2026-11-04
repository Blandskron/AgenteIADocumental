import os
from pathlib import Path
from tempfile import mkstemp

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _publish(path: Path, data: bytes, mode: int, *, replace: bool) -> None:
    fd, filename = mkstemp(dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        temporary.chmod(mode)
        if replace:
            temporary.replace(path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError:
                # Another process already published the private key.
                pass
    finally:
        temporary.unlink(missing_ok=True)


def load_jwt_keys(private_path: Path, public_path: Path) -> tuple[bytes, bytes]:
    if private_path.resolve() == public_path.resolve():
        raise ValueError("JWT private and public keys must use different paths.")

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    if not private_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        _publish(private_path, private_bytes, 0o600, replace=False)

    if os.name == "posix" and private_path.stat().st_mode & 0o077:
        private_path.chmod(0o600)
    private_bytes = private_path.read_bytes()
    key = serialization.load_pem_private_key(private_bytes, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("JWT signing requires an RSA private key.")
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not public_path.exists() or public_path.read_bytes() != public_bytes:
        _publish(public_path, public_bytes, 0o644, replace=True)

    return private_bytes, public_bytes
