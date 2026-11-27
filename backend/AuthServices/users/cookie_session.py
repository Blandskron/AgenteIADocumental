from collections.abc import Mapping

from django.conf import settings
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import Throttled
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .audit_logs import record_audit_log
from .login_protection import audit_auth_event, login_retry_after
from .serializers import CurrentClaimsRefreshSerializer, MyTokenObtainPairSerializer

ACCESS_COOKIE_NAME = "bd_access_token"
REFRESH_COOKIE_NAME = "bd_refresh_token"


def _cookie_flags() -> dict:
    return {
        "httponly": True,
        "secure": bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        "samesite": "Lax",
        "path": "/",
    }


class CookieLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class CookieSessionResponseSerializer(serializers.Serializer):
    authenticated = serializers.BooleanField()
    csrf_token = serializers.CharField()
    user = serializers.DictField(required=False)


class CookieSessionLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Sesión Cookie HttpOnly"],
        request=CookieLoginSerializer,
        responses={200: CookieSessionResponseSerializer},
    )
    def post(self, request):
        data = request.data if isinstance(request.data, Mapping) else {}
        username = data.get("username")
        retry_after = login_retry_after(request, username)
        if retry_after:
            audit_auth_event("login_throttled", channel="cookie")
            raise Throttled(wait=retry_after)

        serializer = MyTokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            audit_auth_event("login_failed", channel="cookie")
            raise

        tokens = serializer.validated_data
        user_obj = getattr(serializer, "user", None)
        csrf_token = get_token(request)
        audit_auth_event("login_succeeded", channel="cookie", actor_id=getattr(user_obj, "pk", None))
        if user_obj is not None:
            record_audit_log(
                action="auth.cookie_login",
                resource_type="user",
                resource_id=str(user_obj.pk),
                actor_user_id=user_obj.pk,
                tenant_id=(tokens.get("user") or {}).get("active_tenant_id"),
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                metadata={"channel": "cookie"},
            )
        response = Response(
            {
                "authenticated": True,
                "csrf_token": csrf_token,
                "user": tokens.get("user", {}),
            },
            status=status.HTTP_200_OK,
        )
        flags = _cookie_flags()
        response.set_cookie(ACCESS_COOKIE_NAME, tokens["access"], max_age=600, **flags)
        response.set_cookie(REFRESH_COOKIE_NAME, tokens["refresh"], max_age=86400, **flags)
        return response


class CookieSessionRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Sesión Cookie HttpOnly"],
        responses={200: CookieSessionResponseSerializer},
    )
    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response({"detail": "Sesión cookie no encontrada."}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = CurrentClaimsRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        csrf_token = get_token(request)
        response = Response({"authenticated": True, "csrf_token": csrf_token}, status=status.HTTP_200_OK)
        flags = _cookie_flags()
        response.set_cookie(ACCESS_COOKIE_NAME, tokens["access"], max_age=600, **flags)
        if "refresh" in tokens:
            response.set_cookie(REFRESH_COOKIE_NAME, tokens["refresh"], max_age=86400, **flags)
        return response


class CookieSessionLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Sesión Cookie HttpOnly"],
        responses={200: CookieSessionResponseSerializer},
    )
    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        response = Response({"authenticated": False, "csrf_token": ""}, status=status.HTTP_200_OK)
        response.delete_cookie(ACCESS_COOKIE_NAME, path="/", samesite="Lax")
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/", samesite="Lax")
        return response

