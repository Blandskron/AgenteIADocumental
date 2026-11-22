"""Active AI provider router (Groq vs local Ollama) and controlled Ollama model management (STB-05)."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from time import time
from urllib.parse import urlsplit

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai_integrations import _resolve_target_tenant
from .audit_logs import record_audit_log
from .login_protection import WINDOW_SECONDS, _consume
from .models import TenantIntegration

AI_ROUTER_PROVIDER = "ai_router"
OLLAMA_PROVIDER = "ollama"
DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_PARAMS = {
    "max_tokens": 1024,
    "temperature": 0.2,
    "timeout_seconds": 120,
}

# Curated CPU-friendly allowlist — prevents arbitrary unverified downloads.
APPROVED_OLLAMA_MODELS = (
    {
        "id": "gemma2:2b",
        "label": "Gemma 2 2B (Ultraligero CPU)",
        "size_gb": 1.6,
        "min_ram_gb": 4,
        "description": "Rápido en CPU con baja memoria; ideal para equipos modestos.",
    },
    {
        "id": "qwen2.5:3b",
        "label": "Qwen 2.5 3B (Recomendado español CPU)",
        "size_gb": 1.9,
        "min_ram_gb": 6,
        "description": "Excelente equilibrio entre comprensión en español y velocidad en CPU.",
    },
    {
        "id": "llama3.2:3b",
        "label": "Llama 3.2 3B (Equilibrado CPU)",
        "size_gb": 2.0,
        "min_ram_gb": 6,
        "description": "Modelo generalista compacto y estable para consultas documentales.",
    },
    {
        "id": "phi3:mini",
        "label": "Phi-3 Mini 3.8B",
        "size_gb": 2.2,
        "min_ram_gb": 6,
        "description": "Buena precisión en razonamiento estructurado sobre documentos técnicos.",
    },
    {
        "id": "mistral:7b",
        "label": "Mistral 7B (Alta calidad, requiere más RAM)",
        "size_gb": 4.1,
        "min_ram_gb": 10,
        "description": "Mayor calidad de síntesis; recomendado en equipos con 12+ GB de RAM.",
    },
)
APPROVED_MODEL_IDS = frozenset(item["id"] for item in APPROVED_OLLAMA_MODELS)
ALLOWED_OLLAMA_HOSTS = frozenset({"ollama", "127.0.0.1", "localhost", "host.docker.internal"})

_PULL_LOCK = threading.Lock()
_PULL_STATES: dict[str, dict] = {}


def validate_ollama_base_url(base_url: str) -> str:
    raw = (base_url or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL de Ollama inválida.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("La URL de Ollama no puede incluir credenciales.")
    host = parsed.hostname.lower()
    configured_host = urlsplit(DEFAULT_OLLAMA_BASE_URL).hostname
    allowed = set(ALLOWED_OLLAMA_HOSTS)
    if configured_host:
        allowed.add(configured_host.lower())
    if host not in allowed:
        raise ValueError("Solo se permiten endpoints locales autorizados para Ollama (ollama / localhost / 127.0.0.1).")
    return raw


def _ollama_http_json(method: str, base_url: str, path: str, payload: dict | None = None, timeout: int = 10) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except ValueError:
            parsed = {"error": raw[:200]}
        return exc.code, parsed


def _run_ollama_pull(base_url: str, model_id: str) -> None:
    req = urllib.request.Request(
        f"{base_url}/api/pull",
        data=json.dumps({"name": model_id, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("error"):
                    with _PULL_LOCK:
                        _PULL_STATES[model_id] = {
                            "model": model_id,
                            "status": "error",
                            "percent": 0,
                            "completed_bytes": 0,
                            "total_bytes": 0,
                            "detail": str(event["error"])[:240],
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    return
                total = int(event.get("total") or 0)
                completed = int(event.get("completed") or 0)
                percent = int(round((completed / total) * 100)) if total > 0 else (100 if event.get("status") == "success" else 0)
                with _PULL_LOCK:
                    _PULL_STATES[model_id] = {
                        "model": model_id,
                        "status": "completed" if event.get("status") == "success" else "downloading",
                        "percent": min(100, max(0, percent)),
                        "completed_bytes": completed,
                        "total_bytes": total,
                        "detail": str(event.get("status") or "downloading")[:120],
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
        with _PULL_LOCK:
            current = _PULL_STATES.get(model_id, {})
            if current.get("status") != "error":
                _PULL_STATES[model_id] = {
                    **current,
                    "model": model_id,
                    "status": "completed",
                    "percent": 100,
                    "detail": "Modelo descargado y listo.",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
    except Exception as exc:
        with _PULL_LOCK:
            _PULL_STATES[model_id] = {
                "model": model_id,
                "status": "error",
                "percent": 0,
                "completed_bytes": 0,
                "total_bytes": 0,
                "detail": f"Error al descargar el modelo desde Ollama: {exc}"[:240],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }


def _serialize_ollama_settings(integration: TenantIntegration | None) -> dict:
    config = dict((integration.config if integration else None) or {})
    params = {**DEFAULT_OLLAMA_PARAMS, **(config.get("params") or {})}
    return {
        "provider": OLLAMA_PROVIDER,
        "enabled": bool(integration and integration.status == "ENABLED"),
        "base_url": config.get("base_url") or DEFAULT_OLLAMA_BASE_URL,
        "model": config.get("model") or DEFAULT_OLLAMA_MODEL,
        "params": params,
        "last_check": config.get("last_check"),
        "updated_at": integration.updated_at.isoformat() if integration and integration.updated_at else None,
    }


class ActiveProviderPatchSerializer(serializers.Serializer):
    active_provider = serializers.ChoiceField(choices=["groq", "ollama"])


class OllamaSettingsPatchSerializer(serializers.Serializer):
    base_url = serializers.CharField(required=False, max_length=256)
    model = serializers.CharField(required=False, max_length=128)
    params = serializers.DictField(required=False)


class OllamaPullRequestSerializer(serializers.Serializer):
    model = serializers.CharField(max_length=128)


class OllamaTestRequestSerializer(serializers.Serializer):
    model = serializers.CharField(required=False, allow_blank=True, max_length=128)


class ActiveAIProviderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"])
    def get(self, request):
        tenant = _resolve_target_tenant(request.user)
        row = TenantIntegration.objects.filter(tenant=tenant, provider=AI_ROUTER_PROVIDER).first()
        active = ((row.config or {}).get("active_provider") if row else None) or "groq"
        return Response({"active_provider": active, "available_providers": ["groq", "ollama"]}, status=status.HTTP_200_OK)

    @extend_schema(tags=["Integraciones IA"], request=ActiveProviderPatchSerializer)
    def patch(self, request):
        tenant = _resolve_target_tenant(request.user)
        serializer = ActiveProviderPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chosen = serializer.validated_data["active_provider"]

        row, _ = TenantIntegration.objects.get_or_create(
            tenant=tenant,
            provider=AI_ROUTER_PROVIDER,
            defaults={"status": "ENABLED", "config": {"active_provider": chosen}},
        )
        row.status = "ENABLED"
        row.config = {**(row.config or {}), "active_provider": chosen}
        row.updated_by_user_id = str(request.user.id)
        row.updated_at = datetime.now(timezone.utc)
        row.save()

        if chosen == OLLAMA_PROVIDER:
            ollama_row, _ = TenantIntegration.objects.get_or_create(
                tenant=tenant,
                provider=OLLAMA_PROVIDER,
                defaults={
                    "status": "ENABLED",
                    "config": {
                        "base_url": DEFAULT_OLLAMA_BASE_URL,
                        "model": DEFAULT_OLLAMA_MODEL,
                        "params": dict(DEFAULT_OLLAMA_PARAMS),
                    },
                },
            )
            if ollama_row.status != "ENABLED":
                ollama_row.status = "ENABLED"
                ollama_row.updated_by_user_id = str(request.user.id)
                ollama_row.updated_at = datetime.now(timezone.utc)
                ollama_row.save()

        record_audit_log(
            action="ai_provider_switch",
            resource_type="tenant_integration",
            resource_id=row.integration_id,
            actor_user_id=request.user.id,
            tenant_id=tenant.tenant_id,
            metadata={"active_provider": chosen},
        )
        return Response({"active_provider": chosen, "available_providers": ["groq", "ollama"]}, status=status.HTTP_200_OK)


class OllamaSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"])
    def get(self, request):
        tenant = _resolve_target_tenant(request.user)
        row = TenantIntegration.objects.filter(tenant=tenant, provider=OLLAMA_PROVIDER).first()
        return Response(_serialize_ollama_settings(row), status=status.HTTP_200_OK)

    @extend_schema(tags=["Integraciones IA"], request=OllamaSettingsPatchSerializer)
    def patch(self, request):
        tenant = _resolve_target_tenant(request.user)
        serializer = OllamaSettingsPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        row, _ = TenantIntegration.objects.get_or_create(
            tenant=tenant,
            provider=OLLAMA_PROVIDER,
            defaults={
                "status": "ENABLED",
                "config": {
                    "base_url": DEFAULT_OLLAMA_BASE_URL,
                    "model": DEFAULT_OLLAMA_MODEL,
                    "params": dict(DEFAULT_OLLAMA_PARAMS),
                },
            },
        )
        cfg = dict(row.config or {})
        if "base_url" in data:
            try:
                cfg["base_url"] = validate_ollama_base_url(data["base_url"])
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if "model" in data:
            model = data["model"].strip()
            if not model:
                return Response({"detail": "Debes indicar un modelo de Ollama."}, status=status.HTTP_400_BAD_REQUEST)
            cfg["model"] = model
        if "params" in data and isinstance(data["params"], dict):
            params = {**DEFAULT_OLLAMA_PARAMS, **(cfg.get("params") or {})}
            if "max_tokens" in data["params"]:
                params["max_tokens"] = max(64, min(8192, int(data["params"]["max_tokens"])))
            if "temperature" in data["params"]:
                params["temperature"] = max(0.0, min(1.5, float(data["params"]["temperature"])))
            if "timeout_seconds" in data["params"]:
                params["timeout_seconds"] = max(10, min(300, int(data["params"]["timeout_seconds"])))
            cfg["params"] = params

        row.status = "ENABLED"
        row.config = cfg
        row.updated_by_user_id = str(request.user.id)
        row.updated_at = datetime.now(timezone.utc)
        row.save()

        record_audit_log(
            action="ai_ollama_settings_write",
            resource_type="tenant_integration",
            resource_id=row.integration_id,
            actor_user_id=request.user.id,
            tenant_id=tenant.tenant_id,
            metadata={"model": cfg.get("model"), "base_url": cfg.get("base_url")},
        )
        return Response(_serialize_ollama_settings(row), status=status.HTTP_200_OK)


class OllamaModelsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"])
    def get(self, request):
        tenant = _resolve_target_tenant(request.user)
        row = TenantIntegration.objects.filter(tenant=tenant, provider=OLLAMA_PROVIDER).first()
        base_url = validate_ollama_base_url(((row.config or {}).get("base_url") if row else None) or DEFAULT_OLLAMA_BASE_URL)
        try:
            code, body = _ollama_http_json("GET", base_url, "/api/tags", timeout=5)
            if code != 200:
                return Response(
                    {
                        "reachable": False,
                        "installed": [],
                        "catalog": list(APPROVED_OLLAMA_MODELS),
                        "reason": f"Ollama respondió HTTP {code}.",
                    },
                    status=status.HTTP_200_OK,
                )
            installed = [
                {
                    "name": item.get("name", ""),
                    "size_bytes": int(item.get("size") or 0),
                    "modified_at": item.get("modified_at"),
                }
                for item in (body.get("models") or [])
                if isinstance(item, dict) and item.get("name")
            ]
            return Response(
                {
                    "reachable": True,
                    "installed": installed,
                    "catalog": list(APPROVED_OLLAMA_MODELS),
                    "reason": None,
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {
                    "reachable": False,
                    "installed": [],
                    "catalog": list(APPROVED_OLLAMA_MODELS),
                    "reason": (
                        "Ollama no está accesible en este momento. Levanta el perfil local con: "
                        "docker compose -f docker/docker-compose.yml -f docker/compose/ollama.yml --profile local-llm up -d"
                    ),
                },
                status=status.HTTP_200_OK,
            )


class OllamaPullView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"], request=OllamaPullRequestSerializer)
    def post(self, request):
        tenant = _resolve_target_tenant(request.user)
        now = int(time())
        if not _consume("ai-ollama-pull", str(request.user.id), now // WINDOW_SECONDS, 5):
            raise Throttled(wait=WINDOW_SECONDS - now % WINDOW_SECONDS)

        serializer = OllamaPullRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model_id = serializer.validated_data["model"].strip()
        if model_id not in APPROVED_MODEL_IDS:
            return Response(
                {
                    "code": "MODEL_NOT_APPROVED",
                    "detail": f"Modelo no autorizado para descarga automática. Permitidos: {sorted(APPROVED_MODEL_IDS)}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        row = TenantIntegration.objects.filter(tenant=tenant, provider=OLLAMA_PROVIDER).first()
        base_url = validate_ollama_base_url(((row.config or {}).get("base_url") if row else None) or DEFAULT_OLLAMA_BASE_URL)

        with _PULL_LOCK:
            current = _PULL_STATES.get(model_id)
            if current and current.get("status") == "downloading":
                return Response(current, status=status.HTTP_202_ACCEPTED)
            initial_state = {
                "model": model_id,
                "status": "downloading",
                "percent": 0,
                "completed_bytes": 0,
                "total_bytes": 0,
                "detail": "Iniciando descarga desde Ollama...",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _PULL_STATES[model_id] = initial_state

        record_audit_log(
            action="ai_ollama_pull",
            resource_type="tenant_integration",
            actor_user_id=request.user.id,
            tenant_id=tenant.tenant_id,
            metadata={"model": model_id},
        )
        worker = threading.Thread(target=_run_ollama_pull, args=(base_url, model_id), daemon=True)
        worker.start()
        return Response(initial_state, status=status.HTTP_202_ACCEPTED)


class OllamaPullStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"])
    def get(self, request):
        _resolve_target_tenant(request.user)
        with _PULL_LOCK:
            items = list(_PULL_STATES.values())
        return Response({"downloads": items}, status=status.HTTP_200_OK)


class OllamaTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Integraciones IA"], request=OllamaTestRequestSerializer)
    def post(self, request):
        tenant = _resolve_target_tenant(request.user)
        serializer = OllamaTestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        row, _ = TenantIntegration.objects.get_or_create(
            tenant=tenant,
            provider=OLLAMA_PROVIDER,
            defaults={
                "status": "ENABLED",
                "config": {
                    "base_url": DEFAULT_OLLAMA_BASE_URL,
                    "model": DEFAULT_OLLAMA_MODEL,
                    "params": dict(DEFAULT_OLLAMA_PARAMS),
                },
            },
        )
        cfg = dict(row.config or {})
        base_url = validate_ollama_base_url(cfg.get("base_url") or DEFAULT_OLLAMA_BASE_URL)
        model = (serializer.validated_data.get("model") or cfg.get("model") or DEFAULT_OLLAMA_MODEL).strip()
        checked_at = datetime.now(timezone.utc).isoformat()

        result_code = "ok"
        reason = None
        try:
            code, body = _ollama_http_json(
                "POST",
                base_url,
                "/v1/chat/completions",
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 4,
                    "temperature": 0.0,
                },
                timeout=30,
            )
            if code != 200:
                result_code = "model" if code == 404 else "provider_error"
                reason = str(body.get("error") or f"Ollama respondió HTTP {code}")[:240]
        except Exception:
            result_code = "network"
            reason = "No se pudo conectar con el servidor local de Ollama."

        cfg["last_check"] = {"at": checked_at, "result": result_code, "reason": reason}
        row.config = cfg
        row.updated_at = datetime.now(timezone.utc)
        row.save()

        record_audit_log(
            action="ai_ollama_test",
            resource_type="tenant_integration",
            resource_id=row.integration_id,
            actor_user_id=request.user.id,
            tenant_id=tenant.tenant_id,
            metadata={"model": model, "result": result_code},
        )
        return Response(
            {"result": result_code, "model": model, "reason": reason, "checked_at": checked_at},
            status=status.HTTP_200_OK,
        )

