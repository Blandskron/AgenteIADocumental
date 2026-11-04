from django.contrib.admin.apps import AdminConfig


class ProtectedAdminConfig(AdminConfig):
    default_site = "core.admin.ProtectedAdminSite"
