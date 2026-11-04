from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F, Q
from django.middleware.csrf import get_token

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission, IsAuthenticated, AllowAny, IsAdminUser, SAFE_METHODS

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from .models import Tenant, TenantArea, TenantGroup, TenantMembership, TenantUserGroup
from .serializers import (
    CurrentClaimsRefreshSerializer,
    GroupSerializer,
    MyTokenObtainPairSerializer,
    PermissionSerializer,
    TenantAreaSerializer,
    TenantGroupSerializer,
    TenantMembershipSerializer,
    TenantSerializer,
    TenantUserGroupSerializer,
    TenantUserProvisionSerializer,
    UserSerializer,
    serialize_user_profile,
)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def user_active_memberships(user):
    return TenantMembership.objects.filter(user_id=str(user.id), status="ACTIVE", tenant__status="ACTIVE")


def tenant_admin_ids(user):
    return set(
        user_active_memberships(user)
        .filter(role="TENANT_ADMIN")
        .values_list("tenant_id", flat=True)
    )


class IsTenantAdminOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or bool(tenant_admin_ids(request.user))

# --- SECCIÓN: USUARIOS (CRUD) ---

@extend_schema(tags=['Usuarios'])
class UserViewSet(viewsets.ModelViewSet):
    """
    Reserva las mutaciones de identidad al superadministrador.
    Los administradores de empresa pueden consultar a sus miembros.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsTenantAdminOrSuperAdmin]

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [IsSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all().order_by("username")
        tenant_ids = tenant_admin_ids(self.request.user)
        user_ids = TenantMembership.objects.filter(tenant_id__in=tenant_ids).values_list("user_id", flat=True)
        return User.objects.filter(id__in=[int(user_id) for user_id in user_ids if str(user_id).isdigit()]).order_by("username")

    @extend_schema(summary="Listar usuarios", description="Obtiene la lista de todos los usuarios.")
    def list(self, request, *args, **kwargs): return super().list(request, *args, **kwargs)

    @extend_schema(summary="Crear usuario", description="Registra un nuevo usuario en el sistema.")
    def create(self, request, *args, **kwargs): return super().create(request, *args, **kwargs)

    @extend_schema(summary="Obtener usuario", description="Recupera los detalles de un usuario específico por ID.")
    def retrieve(self, request, *args, **kwargs): return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Actualizar usuario", description="Actualización completa de un usuario.")
    def update(self, request, *args, **kwargs): return super().update(request, *args, **kwargs)

    @extend_schema(summary="Eliminar usuario", description="Borra permanentemente un usuario.")
    def destroy(self, request, *args, **kwargs): return super().destroy(request, *args, **kwargs)


@extend_schema(tags=['Grupos'])
class GroupViewSet(viewsets.ModelViewSet):
    """
    Gestiona grupos de Django y sus permisos.
    Las mutaciones requieren superadministrador.
    """
    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [IsSuperAdmin()]
        return super().get_permissions()


@extend_schema(tags=['Permisos'])
class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lista permisos disponibles para asignarlos a usuarios o grupos.
    Solo accesible para administradores.
    """
    queryset = Permission.objects.all().order_by("content_type__app_label", "codename")
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminUser]


@extend_schema(tags=['Empresas'])
class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = TenantSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return Tenant.objects.all().order_by("name")

    def perform_create(self, serializer):
        serializer.save(created_by_user_id=str(self.request.user.id))


@extend_schema(tags=['Areas'])
class TenantAreaViewSet(viewsets.ModelViewSet):
    serializer_class = TenantAreaSerializer
    permission_classes = [IsTenantAdminOrSuperAdmin]

    def get_queryset(self):
        queryset = TenantArea.objects.select_related("tenant", "parent_area").order_by("tenant__name", "name")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(parent_area__isnull=True) | Q(parent_area__tenant_id=F("tenant_id")),
            tenant_id__in=tenant_admin_ids(self.request.user),
        )

    def perform_create(self, serializer):
        tenant_id = serializer.validated_data["tenant"].tenant_id
        if not self.request.user.is_superuser and tenant_id not in tenant_admin_ids(self.request.user):
            raise serializers.ValidationError("No tienes permisos para crear areas en esta empresa.")
        serializer.save()


    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Eliminar un área requiere revisar sus referencias documentales.")
        super().perform_destroy(instance)


@extend_schema(tags=['Membresias'])
class TenantMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = TenantMembershipSerializer
    permission_classes = [IsTenantAdminOrSuperAdmin]

    def get_permissions(self):
        if self.action == "create":
            return [IsSuperAdmin()]
        return super().get_permissions()

    @extend_schema(request=TenantUserProvisionSerializer, responses={201: TenantMembershipSerializer})
    @action(detail=False, methods=["post"], url_path="provision", serializer_class=TenantUserProvisionSerializer)
    def provision(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_id = serializer.validated_data["tenant"].pk
        if not request.user.is_superuser and tenant_id not in tenant_admin_ids(request.user):
            raise PermissionDenied("No tienes permisos para crear usuarios en esta empresa.")
        membership = serializer.save()
        return Response(TenantMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        queryset = TenantMembership.objects.select_related("tenant", "area").order_by("tenant__name", "role", "user_id")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(area__isnull=True) | Q(area__tenant_id=F("tenant_id")),
            tenant_id__in=tenant_admin_ids(self.request.user),
        )

    def perform_create(self, serializer):
        serializer.save(created_by_user_id=str(self.request.user.id))

    def perform_update(self, serializer):
        membership = serializer.instance
        if serializer.validated_data.get("user_id", membership.user_id) != membership.user_id:
            raise serializers.ValidationError("El usuario de la membresía es inmutable.")
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        membership = TenantMembership.objects.select_for_update().filter(pk=instance.pk).first()
        if membership is None:
            return
        TenantUserGroup.objects.filter(tenant_id=membership.tenant_id, user_id=membership.user_id).delete()
        super().perform_destroy(membership)


@extend_schema(tags=['Grupos Tenant'])
class TenantGroupViewSet(viewsets.ModelViewSet):
    serializer_class = TenantGroupSerializer
    permission_classes = [IsTenantAdminOrSuperAdmin]

    def get_queryset(self):
        queryset = TenantGroup.objects.select_related("tenant").order_by("tenant__name", "name")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(tenant_id__in=tenant_admin_ids(self.request.user))

    def perform_create(self, serializer):
        tenant_id = serializer.validated_data["tenant"].tenant_id
        if not self.request.user.is_superuser and tenant_id not in tenant_admin_ids(self.request.user):
            raise serializers.ValidationError("No tienes permisos para crear grupos en esta empresa.")
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance = TenantGroup.objects.select_for_update().filter(pk=instance.pk).first()
        if instance is None:
            return
        if not self.request.user.is_superuser and TenantUserGroup.objects.filter(
            group=instance
        ).exclude(tenant=instance.tenant_id).exists():
            raise PermissionDenied("El grupo tiene asignaciones de otra empresa que requieren revisión global.")
        super().perform_destroy(instance)


@extend_schema(tags=['Usuarios en grupos tenant'])
class TenantUserGroupViewSet(viewsets.ModelViewSet):
    serializer_class = TenantUserGroupSerializer
    permission_classes = [IsTenantAdminOrSuperAdmin]

    def get_queryset(self):
        queryset = TenantUserGroup.objects.select_related("tenant", "group").order_by("tenant_id", "user_id")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(
            tenant_id__in=tenant_admin_ids(self.request.user), group__tenant_id=F("tenant_id")
        )

    def perform_create(self, serializer):
        tenant_id = serializer.validated_data["tenant"].tenant_id
        if not self.request.user.is_superuser and tenant_id not in tenant_admin_ids(self.request.user):
            raise serializers.ValidationError("No tienes permisos para asignar grupos en esta empresa.")
        serializer.save()


# --- SECCIÓN: AUTENTICACIÓN ---

class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Inicio de Sesión (JWT)",
        description="Autentica credenciales y entrega tokens con roles y permisos incluidos en el payload.",
        request=inline_serializer(
            name='LoginRequest',
            fields={
                'username': serializers.CharField(),
                'password': serializers.CharField(),
            }
        ),
        responses={
            200: inline_serializer(
                name='LoginResponse',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Credenciales incorrectas")
        },
        tags=['Autenticación']
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        
        if user:
            refresh = MyTokenObtainPairSerializer.get_token(user)
            response = Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': serialize_user_profile(user),
            }, status=status.HTTP_200_OK)
            
            csrf_token = get_token(request)
            response.set_cookie('csrftoken', csrf_token)
            return response
            
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cerrar Sesión",
        description="Invalida el Refresh Token actual enviándolo a la lista negra.",
        request=inline_serializer(
            name='LogoutRequest',
            fields={'refresh': serializers.CharField()}
        ),
        responses={205: OpenApiResponse(description="Sesión cerrada correctamente")},
        tags=['Autenticación']
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'mensaje': 'Logout exitoso'}, status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Perfil del usuario autenticado",
        description="Entrega identidad, grupos, roles y permisos del usuario actual.",
        tags=['AutenticaciÃ³n']
    )
    def get(self, request):
        return Response(serialize_user_profile(request.user), status=status.HTTP_200_OK)


@extend_schema(
    summary="Refrescar Token de Acceso",
    description="Toma un Refresh Token válido y entrega un nuevo Access Token.",
    tags=['Autenticación']
)
class DecoratedTokenRefreshView(TokenRefreshView):
    serializer_class = CurrentClaimsRefreshSerializer


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cambiar contraseña",
        description="Permite al usuario autenticado cambiar su contraseña validando la anterior.",
        request=inline_serializer(
            name='ChangePasswordRequest',
            fields={
                'old_password': serializers.CharField(),
                'new_password': serializers.CharField(),
            }
        ),
        responses={
            200: OpenApiResponse(description="Contraseña cambiada exitosamente"),
            400: OpenApiResponse(description="Datos incorrectos")
        },
        tags=['Autenticación']
    )
    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        
        if not old_password or not new_password:
            return Response({"error": "Ambos campos son requeridos."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.check_password(old_password):
            return Response({"error": "La contraseña actual es incorrecta."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user.set_password(new_password)
            user.save()
            return Response({"mensaje": "Contraseña actualizada correctamente."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
