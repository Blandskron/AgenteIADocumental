from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ChangePasswordView,
    DecoratedTokenRefreshView,
    GroupViewSet,
    LoginView,
    LogoutView,
    MeView,
    PermissionViewSet,
    TenantAreaViewSet,
    TenantGroupViewSet,
    TenantMembershipViewSet,
    TenantViewSet,
    TenantUserGroupViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'crud', UserViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'tenant-areas', TenantAreaViewSet, basename='tenant-area')
router.register(r'tenant-memberships', TenantMembershipViewSet, basename='tenant-membership')
router.register(r'tenant-groups', TenantGroupViewSet, basename='tenant-group')
router.register(r'tenant-user-groups', TenantUserGroupViewSet, basename='tenant-user-group')

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('token/refresh/', DecoratedTokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
