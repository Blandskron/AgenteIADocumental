import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from unittest import skipUnless

from django.test import SimpleTestCase
import jwt

from .jwt_keys import load_jwt_keys


class JwtKeyTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.private = root / "signing" / "private.pem"
        self.public = root / "verification" / "public.pem"

    def test_republishes_public_key_without_replacing_private_key(self):
        pair = load_jwt_keys(self.private, self.public)
        self.public.unlink()
        self.assertEqual(load_jwt_keys(self.private, self.public), pair)
        self.public.write_bytes(b"stale public key")
        self.assertEqual(load_jwt_keys(self.private, self.public), pair)
        self.assertEqual(self.public.read_bytes(), pair[1])

    @skipUnless(os.name == "posix", "POSIX permissions")
    def test_signing_key_has_owner_only_permissions(self):
        load_jwt_keys(self.private, self.public)
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.public.stat().st_mode), 0o644)

    def test_shared_file_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different paths"):
            load_jwt_keys(self.private, self.private)

    def test_new_volume_pair_rejects_tokens_signed_by_legacy_key(self):
        old_private, old_public = load_jwt_keys(self.private, self.public)
        new_private, new_public = load_jwt_keys(
            self.private.with_name("new-private.pem"), self.public.with_name("new-public.pem")
        )
        claims = {"sub": "synthetic-user", "token_type": "access"}
        old_token = jwt.encode(claims, old_private, algorithm="RS256")
        new_token = jwt.encode(claims, new_private, algorithm="RS256")
        self.assertEqual(jwt.decode(old_token, old_public, algorithms=["RS256"]), claims)
        self.assertEqual(jwt.decode(new_token, new_public, algorithms=["RS256"]), claims)
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(old_token, new_public, algorithms=["RS256"])
