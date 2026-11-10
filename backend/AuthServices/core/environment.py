from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def load_environment(environ, base_dir):
    mode = environ.get("AUTH_ENV", "development")
    if mode not in {"development", "production"}:
        raise ImproperlyConfigured("AUTH_ENV must be development or production.")
    production = mode == "production"

    def required(name, development_default):
        if not production:
            return environ.get(name, development_default)
        value = environ.get(name)
        if not value or not value.strip():
            raise ImproperlyConfigured(f"{name} is required in production.")
        return value

    def entries(value):
        return [item.strip() for item in value.split(",") if item.strip()]

    secret = required("DJANGO_SECRET_KEY", "django-insecure-blandskron-development-only")
    hosts = entries(required("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,auth-service"))
    origins = entries(environ.get(
        "DJANGO_CORS_ALLOWED_ORIGINS", "" if production else "http://localhost:3000,http://127.0.0.1:3000"
    ))
    database_user = required("POSTGRES_USER", "postgres")
    database_password = required("POSTGRES_PASSWORD", "")
    private_key_path = Path(required("DJANGO_PRIVATE_KEY_PATH", str(base_dir / "private.pem")))
    public_key_path = Path(required("DJANGO_PUBLIC_KEY_PATH", str(base_dir / "public.pem")))

    if production:
        if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith("django-insecure-"):
            raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a strong production secret.")
        if not hosts or any("*" in host or host.startswith(".") for host in hosts):
            raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list explicit production hosts.")
        if database_user.strip().casefold() == "postgres" or len(database_password) < 16:
            raise ImproperlyConfigured("Use a dedicated database role and a strong password in production.")
        if not private_key_path.is_file():
            raise ImproperlyConfigured("Provision the JWT private key before starting production Auth.")
        for origin in origins:
            try:
                url = urlsplit(origin)
                valid = (
                    url.scheme == "https" and url.hostname and url.username is None
                    and not (url.path or url.query or url.fragment) and url.port != 0
                )
            except ValueError:
                valid = False
            if not valid:
                raise ImproperlyConfigured("DJANGO_CORS_ALLOWED_ORIGINS must list HTTPS origins in production.")

    return {
        "production": production,
        "secret": secret,
        "hosts": hosts,
        "origins": origins,
        "private_key_path": private_key_path,
        "public_key_path": public_key_path,
        "database": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": required("POSTGRES_DB", "documents_db"),
            "USER": database_user,
            "PASSWORD": database_password,
            "HOST": required("POSTGRES_HOST", "localhost"),
            "PORT": environ.get("POSTGRES_PORT", "5432"),
        },
    }
