import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from time import time

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit_logs import record_audit_log
from .login_protection import WINDOW_SECONDS, _consume, audit_auth_event
from .models import Tenant, TenantIntegration
from .secrets_cipher import SecretDecryptionError, SecretsCipher
from .serializers import serialize_user_profile
from .views import user_can_manage_ai_settings

GROQ_PROVIDER = "groq"
GROQ_API_BASE_URL = os.environ.get("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_PROBE_TIMEOUT_SECONDS = 10
GROQ_TEST_RATE_LIMIT = 5
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_PARAMS = {
    "max_tokens": 2000,
    "temperature": 0.3,
    "timeout_seconds": 60,
}

NON_CHAT_MODEL_KEYWORDS = ("whisper", "tts", "guard", "prompt-guard", "playai", "orpheus")


def _ai_test_retry_after(user_id: int) -> int:
    now = int(time())
    window = now // WINDOW_SECONDS
    if _consume("ai-groq-test", str(user_id), window, GROQ_TEST_RATE_LIMIT):
        return 0
    return WINDOW_SECONDS - now % WINDOW_SECONDS


def _get_cipher() -> SecretsCipher | None:
    return SecretsCipher.from_environ(os.environ)


def _resolve_target_tenant(user) -> Tenant:
    profile = serialize_user_profile(user)
    active_tenant_id = profile["active_tenant_id"]
    if active_tenant_id:
        if not user_can_manage_ai_settings(user, tenant_id=active_tenant_id):
            raise PermissionDenied("No tienes permisos para administrar la configuración de IA.")
        tenant = Tenant.objects.filter(tenant_id=active_tenant_id, status="ACTIVE").first()
        if tenant is None:
            raise PermissionDenied("Empresa activa no disponible.")
        return tenant
    if user.is_superuser:
        tenant = Tenant.objects.filter(status="ACTIVE").order_by("created_at").first()
        if tenant is not None:
            return tenant
        raise PermissionDenied("Crea o asigna una empresa activa antes de configurar integraciones de IA.")
    raise PermissionDenied("No tienes permisos para administrar la configuración de IA.")


def _extract_encrypted_api_key(integration: TenantIntegration | None) -> str | None:
    if not integration or not integration.secrets_encrypted:
        return None
    raw = integration.secrets_encrypted
    if raw.startswith("secrets1."):
        return raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("api_key"), str):
            return parsed["api_key"]
    except ValueError:
        return None
    return None


def _decrypt_api_key(integration: TenantIntegration | None, cipher: SecretsCipher | None) -> tuple[str | None, str | None]:
    """Returns (plaintext_key, error_code)."""
    encrypted = _extract_encrypted_api_key(integration)
    if not encrypted:
        return None, "not_configured"
    if cipher is None:
        return None, "encryption_unavailable"
    try:
        return cipher.decrypt(encrypted), None
    except SecretDecryptionError:
        return None, "decryption_error"


def _effective_status(integration: TenantIntegration | None, has_secret: bool, decrypt_error: str | None) -> str:
    if not integration or not has_secret:
        return "not_configured"
    if decrypt_error:
        return "error"
    last_check = (integration.config or {}).get("last_check") or {}
    result = last_check.get("result")
    if result == "ok":
        return "connected"
    if result in {"auth", "model", "rate_limited", "network", "timeout", "provider_error"}:
        return "error"
    return "ready_to_test"


def _serialize_groq_settings(integration: TenantIntegration | None, cipher: SecretsCipher | None) -> dict:
    config = dict((integration.config if integration else None) or {})
    encrypted = _extract_encrypted_api_key(integration)
    has_secret = bool(encrypted)
    plaintext, decrypt_error = _decrypt_api_key(integration, cipher) if has_secret else (None, None)

    fingerprint = config.get("key_fingerprint")
    if plaintext and not fingerprint:
        fingerprint = SecretsCipher.fingerprint(plaintext)

    last_check = config.get("last_check")
    if decrypt_error and not last_check:
        last_check = {"at": None, "result": decrypt_error}

    return {
        "provider": GROQ_PROVIDER,
        "configured": has_secret and decrypt_error is None,
        "status": _effective_status(integration, has_secret, decrypt_error),
        "model": config.get("model") or DEFAULT_GROQ_MODEL,
        "params": {
            "max_tokens": int(config.get("max_tokens", DEFAULT_GROQ_PARAMS["max_tokens"])),
            "temperature": float(config.get("temperature", DEFAULT_GROQ_PARAMS["temperature"])),
            "timeout_seconds": int(config.get("timeout_seconds", DEFAULT_GROQ_PARAMS["timeout_seconds"])),
        },
        "last_check": last_check,
        "key_fingerprint": fingerprint if has_secret else None,
        "encryption_ready": cipher is not None,
        "updated_at": integration.updated_at.isoformat() if integration and integration.updated_at else None,
    }


def _groq_http_request(method: str, path: str, api_key: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{GROQ_API_BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=GROQ_PROBE_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except ValueError:
            parsed = {}
        return exc.code, parsed
    except TimeoutError:
        return 504, {"error": {"message": "Timeout contacting Groq."}}
    except urllib.error.URLError:
        return 502, {"error": {"message": "Network error contacting Groq."}}


def _is_chat_model(model_entry: dict) -> bool:
    model_id = str(model_entry.get("id") or "").strip()
    if not model_id:
        return False
    lowered = model_id.lower()
    if any(keyword in lowered for keyword in NON_CHAT_MODEL_KEYWORDS):
        return False
    return model_entry.get("active", True) is not False


def fetch_groq_chat_models(api_key: str) -> tuple[str, list[str], str | None]:
    """Returns (result_code, model_ids, reason)."""
    code, body = _groq_http_request("GET", "/models", api_key)
    if code == 200:
        raw_models = body.get("data") if isinstance(body, dict) else []
        models = sorted({
            str(item["id"]).strip()
            for item in (raw_models or [])
            if isinstance(item, dict) and _is_chat_model(item)
        })
        return "ok", models, None
    if code in (401, 403):
        return "auth", [], "La clave API de Groq fue rechazada por el proveedor."
    if code == 429:
        return "rate_limited", [], "Groq reportó límite de tasa (rate limit). Intenta nuevamente en unos segundos."
    if code == 504:
        return "timeout", [], "Tiempo de espera agotado al consultar Groq."
    if code == 502:
        return "network", [], "No fue posible conectar con el servicio de Groq."
    return "provider_error", [], "Groq devolvió un error inesperado al listar modelos."


def probe_groq_completion(api_key: str, model: str) -> tuple[str, str | None]:
    """Minimal 1-token synthetic probe without any document content."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_completion_tokens": 1,
        "temperature": 0,
    }
    code, _ = _groq_http_request("POST", "/chat/completions", api_key, payload=payload)
    if code == 200:
        return "ok", None
    if code in (401, 403):
        return "auth", "La clave API de Groq fue rechazada por el proveedor."
    if code in (400, 404):
        return "model", f"El modelo '{model}' no está disponible o no es válido en Groq."
    if code == 429:
        return "rate_limited", "Groq reportó límite de tasa (rate limit) durante la prueba."
    if code == 504:
        return "timeout", "Tiempo de espera agotado al probar el modelo en Groq."
    if code == 502:
        return "network", "No fue posible conectar con el servicio de Groq."
    return "provider_error", "Groq devolvió un error inesperado durante la prueba."


# --- Serializers (OpenAPI-safe, zero secret leakage) ---

class GroqParamsSerializer(serializers.Serializer):
    max_tokens = serializers.IntegerField(min_value=64, max_value=8192, required=False)
    temperature = serializers.FloatField(min_value=0.0, max_value=1.5, required=False)
    timeout_seconds = serializers.IntegerField(min_value=5, max_value=180, required=False)


class GroqLastCheckSerializer(serializers.Serializer):
    at = serializers.CharField(allow_null=True, required=False)
    result = serializers.CharField()
    reason = serializers.CharField(allow_null=True, required=False)


class GroqSettingsResponseSerializer(serializers.Serializer):
    provider = serializers.CharField()
    configured = serializers.BooleanField()
    status = serializers.CharField()
    model = serializers.CharField()
    params = GroqParamsSerializer()
    last_check = GroqLastCheckSerializer(allow_null=True)
    key_fingerprint = serializers.CharField(allow_null=True)
    encryption_ready = serializers.BooleanField()
    updated_at = serializers.CharField(allow_null=True)


class GroqSettingsPatchSerializer(serializers.Serializer):
    model = serializers.CharField(min_length=2, max_length=128, required=False)
    params = GroqParamsSerializer(required=False)


class GroqCredentialsPutSerializer(serializers.Serializer):
    api_key = serializers.CharField(min_length=8, max_length=512, write_only=True, trim_whitespace=True)


class GroqModelsResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    models = serializers.ListField(child=serializers.CharField())
    reason = serializers.CharField(allow_null=True, required=False)


class GroqTestRequestSerializer(serializers.Serializer):
    model = serializers.CharField(min_length=2, max_length=128, required=False)


class GroqTestResponseSerializer(serializers.Serializer):
    result = serializers.CharField()
    model = serializers.CharField()
    models = serializers.ListField(child=serializers.CharField(), required=False)
    reason = serializers.CharField(allow_null=True, required=False)
    checked_at = serializers.CharField()


# --- Views ---

class GroqSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Integraciones IA"],
        responses={200: GroqSettingsResponseSerializer},
    )
    def get(self, request):
        tenant = _resolve_target_tenant(request.user)
        integration = TenantIntegration.objects.filter(tenant=tenant, provider=GROQ_PROVIDER).first()
        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        return Response(_serialize_groq_settings(integration, cipher), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Integraciones IA"],
        request=GroqSettingsPatchSerializer,
        responses={200: GroqSettingsResponseSerializer},
    )
    def patch(self, request):
        tenant = _resolve_target_tenant(request.user)
        serializer = GroqSettingsPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        with transaction.atomic():
            integration, _ = TenantIntegration.objects.get_or_create(
                tenant=tenant,
                provider=GROQ_PROVIDER,
                defaults={"status": "DISABLED", "config": {}},
            )
            config = dict(integration.config or {})
            if "model" in validated:
                config["model"] = validated["model"].strip()
            if "params" in validated:
                for key in ("max_tokens", "temperature", "timeout_seconds"):
                    if key in validated["params"]:
                        config[key] = validated["params"][key]
            integration.config = config
            integration.updated_by_user_id = str(request.user.id)
            integration.save(update_fields=["config", "updated_by_user_id", "updated_at"])

        audit_auth_event(
            "ai_settings_write",
            actor_id=request.user.pk,
            tenant_id=tenant.tenant_id,
            provider=GROQ_PROVIDER,
            action="patch_config",
            result="ok",
        )
        try:
            record_audit_log(
                action="ai_settings_write",
                resource_type="tenant_integration",
                resource_id=integration.integration_id,
                actor_user_id=request.user.pk,
                tenant_id=tenant.tenant_id,
                metadata={"provider": GROQ_PROVIDER, "sub_action": "patch_config", "model": config.get("model")},
            )
        except Exception:
            pass
        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        return Response(_serialize_groq_settings(integration, cipher), status=status.HTTP_200_OK)


class GroqCredentialsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Integraciones IA"],
        request=GroqCredentialsPutSerializer,
        responses={
            200: GroqSettingsResponseSerializer,
            503: OpenApiResponse(description="SECRETS_ENCRYPTION_KEY no configurada."),
        },
    )
    def put(self, request):
        tenant = _resolve_target_tenant(request.user)
        serializer = GroqCredentialsPutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key = serializer.validated_data["api_key"]

        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        if cipher is None:
            return Response(
                {
                    "detail": "El cifrado de secretos (SECRETS_ENCRYPTION_KEY) no está configurado en el servidor.",
                    "code": "ENCRYPTION_NOT_CONFIGURED",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        encrypted = cipher.encrypt(api_key)
        fingerprint = SecretsCipher.fingerprint(api_key)

        with transaction.atomic():
            integration, _ = TenantIntegration.objects.get_or_create(
                tenant=tenant,
                provider=GROQ_PROVIDER,
                defaults={"status": "ENABLED", "config": {}},
            )
            config = dict(integration.config or {})
            config["key_fingerprint"] = fingerprint
            config.pop("last_check", None)
            integration.config = config
            integration.secrets_encrypted = encrypted
            integration.status = "ENABLED"
            integration.updated_by_user_id = str(request.user.id)
            integration.save(
                update_fields=["config", "secrets_encrypted", "status", "updated_by_user_id", "updated_at"]
            )

        audit_auth_event(
            "ai_settings_write",
            actor_id=request.user.pk,
            tenant_id=tenant.tenant_id,
            provider=GROQ_PROVIDER,
            action="put_credentials",
            key_fingerprint=fingerprint,
            result="ok",
        )
        try:
            record_audit_log(
                action="ai_settings_write",
                resource_type="tenant_integration",
                resource_id=integration.integration_id,
                actor_user_id=request.user.pk,
                tenant_id=tenant.tenant_id,
                metadata={"provider": GROQ_PROVIDER, "sub_action": "put_credentials", "key_fingerprint": fingerprint},
            )
        except Exception:
            pass
        return Response(_serialize_groq_settings(integration, cipher), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Integraciones IA"],
        responses={200: GroqSettingsResponseSerializer},
    )
    def delete(self, request):
        tenant = _resolve_target_tenant(request.user)
        with transaction.atomic():
            integration = TenantIntegration.objects.filter(tenant=tenant, provider=GROQ_PROVIDER).first()
            if integration is not None:
                config = dict(integration.config or {})
                config.pop("key_fingerprint", None)
                config.pop("last_check", None)
                integration.config = config
                integration.secrets_encrypted = None
                integration.status = "DISABLED"
                integration.updated_by_user_id = str(request.user.id)
                integration.save(
                    update_fields=["config", "secrets_encrypted", "status", "updated_by_user_id", "updated_at"]
                )

        audit_auth_event(
            "ai_settings_write",
            actor_id=request.user.pk,
            tenant_id=tenant.tenant_id,
            provider=GROQ_PROVIDER,
            action="delete_credentials",
            result="ok",
        )
        try:
            record_audit_log(
                action="ai_settings_write",
                resource_type="tenant_integration",
                resource_id=integration.integration_id if integration else None,
                actor_user_id=request.user.pk,
                tenant_id=tenant.tenant_id,
                metadata={"provider": GROQ_PROVIDER, "sub_action": "delete_credentials"},
            )
        except Exception:
            pass
        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        return Response(_serialize_groq_settings(integration, cipher), status=status.HTTP_200_OK)


class GroqModelsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Integraciones IA"],
        responses={200: GroqModelsResponseSerializer},
    )
    def get(self, request):
        tenant = _resolve_target_tenant(request.user)
        integration = TenantIntegration.objects.filter(tenant=tenant, provider=GROQ_PROVIDER).first()
        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        api_key, err = _decrypt_api_key(integration, cipher)
        if err or not api_key:
            return Response(
                {"result": err or "not_configured", "models": [], "reason": "No hay una clave Groq activa disponible."},
                status=status.HTTP_200_OK,
            )
        result_code, models, reason = fetch_groq_chat_models(api_key)
        return Response({"result": result_code, "models": models, "reason": reason}, status=status.HTTP_200_OK)


class GroqTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Integraciones IA"],
        request=GroqTestRequestSerializer,
        responses={200: GroqTestResponseSerializer},
    )
    def post(self, request):
        tenant = _resolve_target_tenant(request.user)
        retry_after = _ai_test_retry_after(request.user.pk)
        if retry_after > 0:
            raise Throttled(wait=retry_after, detail="Demasiadas pruebas de conexión. Espera un minuto.")

        serializer = GroqTestRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        integration = TenantIntegration.objects.filter(tenant=tenant, provider=GROQ_PROVIDER).first()
        try:
            cipher = _get_cipher()
        except ValueError:
            cipher = None
        api_key, err = _decrypt_api_key(integration, cipher)
        checked_at = datetime.now(timezone.utc).isoformat()
        model = serializer.validated_data.get("model") or (
            (integration.config or {}).get("model") if integration else None
        ) or DEFAULT_GROQ_MODEL

        if err or not api_key:
            audit_auth_event(
                "ai_settings_test",
                actor_id=request.user.pk,
                tenant_id=tenant.tenant_id,
                provider=GROQ_PROVIDER,
                result=err or "not_configured",
            )
            return Response(
                {
                    "result": err or "not_configured",
                    "model": model,
                    "models": [],
                    "reason": "Configura y guarda una clave API de Groq antes de probar la conexión.",
                    "checked_at": checked_at,
                },
                status=status.HTTP_200_OK,
            )

        models_result, models, models_reason = fetch_groq_chat_models(api_key)
        if models_result != "ok":
            final_result, final_reason = models_result, models_reason
        else:
            final_result, final_reason = probe_groq_completion(api_key, model)

        if integration is not None:
            config = dict(integration.config or {})
            config["last_check"] = {"at": checked_at, "result": final_result, "reason": final_reason}
            integration.config = config
            integration.updated_by_user_id = str(request.user.id)
            integration.save(update_fields=["config", "updated_by_user_id", "updated_at"])

        audit_auth_event(
            "ai_settings_test",
            actor_id=request.user.pk,
            tenant_id=tenant.tenant_id,
            provider=GROQ_PROVIDER,
            model=model,
            result=final_result,
        )
        try:
            record_audit_log(
                action="ai_settings_test",
                resource_type="tenant_integration",
                resource_id=integration.integration_id if integration else None,
                actor_user_id=request.user.pk,
                tenant_id=tenant.tenant_id,
                metadata={"provider": GROQ_PROVIDER, "model": model, "result": final_result},
            )
        except Exception:
            pass
        return Response(
            {
                "result": final_result,
                "model": model,
                "models": models,
                "reason": final_reason,
                "checked_at": checked_at,
            },
            status=status.HTTP_200_OK,
        )

