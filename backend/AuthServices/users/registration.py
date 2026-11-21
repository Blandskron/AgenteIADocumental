"""Public registration, transactional initial-admin bootstrap, and honest password-reset status (STB-03)."""

from __future__ import annotations

import os
import re

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .audit_logs import record_audit_log
from .models import Tenant, TenantMembership
from .serializers import serialize_user_profile


USERNAME_CLEAN_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def is_smtp_configured() -> bool:
    return bool((os.environ.get("EMAIL_HOST") or "").strip())


def is_google_oidc_enabled() -> bool:
    return bool((os.environ.get("GOOGLE_OIDC_CLIENT_ID") or "").strip())


def _issue_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    profile = serialize_user_profile(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": profile,
    }


def _derive_username(email: str, requested_username: str = "") -> str:
    base = (requested_username or "").strip()
    if not base:
        base = email.split("@", 1)[0]
    cleaned = USERNAME_CLEAN_RE.sub("", base)[:120] or "usuario"
    candidate = cleaned
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{cleaned[:110]}_{suffix}"
        suffix += 1
    return candidate


class SetupStatusResponseSerializer(serializers.Serializer):
    needs_setup = serializers.BooleanField()
    google_login_enabled = serializers.BooleanField()
    google_client_id = serializers.CharField(allow_null=True)
    smtp_configured = serializers.BooleanField()


class RegisterRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    workspace_name = serializers.CharField(required=False, allow_blank=True, max_length=120)


class RegisterResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()
    is_initial_admin = serializers.BooleanField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SetupStatusView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Autenticación"], responses={200: SetupStatusResponseSerializer})
    def get(self, request):
        google_client_id = (os.environ.get("GOOGLE_OIDC_CLIENT_ID") or "").strip() or None
        return Response(
            {
                "needs_setup": not User.objects.filter(is_superuser=True).exists(),
                "google_login_enabled": bool(google_client_id),
                "google_client_id": google_client_id,
                "smtp_configured": is_smtp_configured(),
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Autenticación"],
        request=RegisterRequestSerializer,
        responses={201: RegisterResponseSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data["email"].strip().lower()
        requested_username = (data.get("username") or "").strip()
        password = data["password"]
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        workspace_name = (data.get("workspace_name") or "").strip() or "Espacio principal"

        # Serialize concurrent bootstrap registrations across workers/requests.
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ["blandskron.auth.bootstrap"])

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"detail": "Ya existe una cuenta registrada con ese correo electrónico."},
                status=status.HTTP_409_CONFLICT,
            )
        if requested_username and User.objects.filter(username__iexact=requested_username).exists():
            return Response(
                {"detail": "El nombre de usuario ya está en uso."},
                status=status.HTTP_409_CONFLICT,
            )

        username = requested_username or _derive_username(email)
        is_first_account = not User.objects.exists()

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_staff=is_first_account,
            is_superuser=is_first_account,
        )
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()

        tenant_id = None
        if is_first_account:
            tenant = Tenant.objects.filter(status="ACTIVE").order_by("created_at").first()
            if tenant is None:
                tenant = Tenant.objects.create(name=workspace_name, status="ACTIVE")
            TenantMembership.objects.create(
                tenant=tenant,
                user_id=str(user.id),
                role="TENANT_ADMIN",
                status="ACTIVE",
            )
            tenant_id = tenant.tenant_id

        record_audit_log(
            action="auth.initial_bootstrap_register" if is_first_account else "auth.register",
            resource_type="user",
            resource_id=str(user.id),
            actor_user_id=user.id,
            tenant_id=tenant_id,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            metadata={"is_initial_admin": is_first_account},
        )

        payload = _issue_tokens_for_user(user)
        payload["is_initial_admin"] = is_first_account
        return Response(payload, status=status.HTTP_201_CREATED)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Autenticación"], request=PasswordResetRequestSerializer)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not is_smtp_configured():
            return Response(
                {
                    "code": "SMTP_NOT_CONFIGURED",
                    "detail": (
                        "La recuperación automática por correo requiere configurar un servidor SMTP (EMAIL_HOST). "
                        "Por seguridad no se permite restablecer contraseñas sin verificación; solicita a un "
                        "administrador del espacio que restablezca tu acceso."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Generic non-enumerating response when SMTP is configured.
        return Response(
            {
                "status": "accepted",
                "detail": "Si el correo existe en la plataforma, recibirás instrucciones para restablecer tu acceso.",
            },
            status=status.HTTP_200_OK,
        )

