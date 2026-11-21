"""Optional Google OpenID Connect (OAuth 2.0) login for AuthServices (STB-04)."""

from __future__ import annotations

import json
import os
import urllib.request
from urllib.parse import urlsplit

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit_logs import record_audit_log
from .registration import _derive_username, _issue_tokens_for_user

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


def _allowed_redirect_origins() -> set[str]:
    origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []) or [])
    extra = (os.environ.get("GOOGLE_OIDC_ALLOWED_ORIGINS") or "").split(",")
    for item in extra:
        cleaned = item.strip().rstrip("/")
        if cleaned:
            origins.add(cleaned)
    return {origin.rstrip("/") for origin in origins if origin}


def validate_redirect_uri(redirect_uri: str | None) -> None:
    if not redirect_uri:
        return
    parsed = urlsplit(redirect_uri.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("redirect_uri inválido.")
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if origin not in _allowed_redirect_origins():
        raise ValueError("redirect_uri no pertenece a un origen autorizado.")


def _fetch_google_jwks() -> dict:
    req = urllib.request.Request(GOOGLE_JWKS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_google_id_token(id_token: str, client_id: str, expected_nonce: str | None = None) -> dict:
    """Verifies RS256 signature, issuer, audience, expiration, email_verified and optional nonce."""
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    jwks = _fetch_google_jwks()
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        raise ValueError("No se pudieron cargar las claves públicas de Google.")

    jwk_match = next((k for k in keys if k.get("kid") == kid), None) if kid else (keys[0] if keys else None)
    if not jwk_match:
        raise ValueError("Clave pública de Google no encontrada para el token recibido.")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_match))
    claims = jwt.decode(
        id_token,
        key=public_key,
        algorithms=["RS256"],
        audience=client_id,
        options={"require": ["exp", "iss", "sub", "email"]},
    )
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ValueError("Emisor de token Google no autorizado.")
    if claims.get("email_verified") is not True:
        raise ValueError("La cuenta de Google no tiene un correo verificado.")
    if expected_nonce and claims.get("nonce") != expected_nonce:
        raise ValueError("Nonce OIDC inválido.")
    return claims


class GoogleLoginRequestSerializer(serializers.Serializer):
    id_token = serializers.CharField(min_length=20)
    nonce = serializers.CharField(required=False, allow_blank=True)
    redirect_uri = serializers.CharField(required=False, allow_blank=True)


class GoogleOidcLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Autenticación"], request=GoogleLoginRequestSerializer)
    @transaction.atomic
    def post(self, request):
        client_id = (os.environ.get("GOOGLE_OIDC_CLIENT_ID") or "").strip()
        if not client_id:
            return Response(
                {
                    "code": "GOOGLE_LOGIN_DISABLED",
                    "detail": "El inicio de sesión con Google no está habilitado en esta instalación.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = GoogleLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            validate_redirect_uri(data.get("redirect_uri"))
            claims = verify_google_id_token(
                data["id_token"],
                client_id=client_id,
                expected_nonce=(data.get("nonce") or "").strip() or None,
            )
        except (ValueError, jwt.PyJWTError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        email = str(claims["email"]).strip().lower()
        first_name = str(claims.get("given_name") or "")[:150]
        last_name = str(claims.get("family_name") or "")[:150]

        user = User.objects.filter(email__iexact=email).first()
        created = False
        if user is None:
            # Never grant administrative privileges merely for authenticating with Google.
            user = User(
                username=_derive_username(email),
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
            user.set_unusable_password()
            user.save()
            created = True
        elif not user.is_active:
            return Response({"detail": "Tu cuenta está deshabilitada."}, status=status.HTTP_403_FORBIDDEN)

        record_audit_log(
            action="auth.google_login",
            resource_type="user",
            resource_id=str(user.id),
            actor_user_id=user.id,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            metadata={"created": created, "google_sub": str(claims.get("sub", ""))[:64]},
        )

        payload = _issue_tokens_for_user(user)
        payload["created"] = created
        return Response(payload, status=status.HTTP_200_OK)

