from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .environment import load_environment


class AuthEnvironmentTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.private = self.root / "private.pem"
        self.private.touch()
        self.production = {
            "AUTH_ENV": "production",
            "DJANGO_SECRET_KEY": "synthetic-test-secret-with-enough-length-and-variety-001",
            "DJANGO_ALLOWED_HOSTS": " auth.example.com , internal.example.com ",
            "DJANGO_PRIVATE_KEY_PATH": str(self.private),
            "DJANGO_PUBLIC_KEY_PATH": str(self.root / "public.pem"),
            "POSTGRES_USER": "auth_runtime",
            "POSTGRES_PASSWORD": "synthetic-database-password",
            "POSTGRES_DB": "documents_db",
            "POSTGRES_HOST": "db.example.com",
        }

    def test_development_defaults_use_local_hosts(self):
        config = load_environment({}, self.root)
        self.assertFalse(config["production"])
        self.assertEqual(config["hosts"], ["localhost", "127.0.0.1", "auth-service"])

    def test_production_accepts_explicit_configuration_and_no_cors_by_default(self):
        config = load_environment(self.production, self.root)
        self.assertTrue(config["production"])
        self.assertEqual(config["hosts"], ["auth.example.com", "internal.example.com"])
        self.assertEqual(config["origins"], [])
        self.assertEqual(config["database"]["USER"], "auth_runtime")
        self.assertEqual(config["private_key_path"], self.private)

    def test_production_rejects_missing_or_unsafe_configuration(self):
        for name, value in (
            ("AUTH_ENV", "prod"),
            ("DJANGO_SECRET_KEY", "change-me-in-production"),
            ("DJANGO_ALLOWED_HOSTS", "*"),
            ("DJANGO_ALLOWED_HOSTS", ","),
            ("DJANGO_ALLOWED_HOSTS", ".example.com"),
            ("POSTGRES_USER", "postgres"),
            ("POSTGRES_PASSWORD", "admin1234"),
            ("POSTGRES_HOST", ""),
            ("DJANGO_PRIVATE_KEY_PATH", str(self.root / "missing.pem")),
            ("DJANGO_CORS_ALLOWED_ORIGINS", "http://auth.example.com"),
            ("DJANGO_CORS_ALLOWED_ORIGINS", "https://auth.example.com/path"),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(ImproperlyConfigured):
                load_environment({**self.production, name: value}, self.root)

    def test_production_accepts_https_cors_origins(self):
        config = load_environment(
            {**self.production, "DJANGO_CORS_ALLOWED_ORIGINS": "https://app.example.com"}, self.root
        )
        self.assertEqual(config["origins"], ["https://app.example.com"])
