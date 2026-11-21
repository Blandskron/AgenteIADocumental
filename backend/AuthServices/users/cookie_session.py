from django.conf import settings
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

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
        serializer = MyTokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        csrf_token = get_token(request)
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

