from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .google_oidc import GoogleOidcLoginView
from .registration import PasswordResetRequestView, RegisterView, SetupStatusView
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
    path('setup-status/', SetupStatusView.as_view(), name='setup_status'),
    path('register/', RegisterView.as_view(), name='register'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('google/login/', GoogleOidcLoginView.as_view(), name='google_oidc_login'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('token/refresh/', DecoratedTokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]
