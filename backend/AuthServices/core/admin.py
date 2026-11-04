from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError


class ProtectedAdminAuthenticationForm(AdminAuthenticationForm):
    def clean(self):
        from users.login_protection import audit_auth_event, login_retry_after

        if self.request is not None and login_retry_after(self.request, self.cleaned_data.get("username")):
            audit_auth_event("login_throttled", channel="django_admin")
            raise ValidationError("Demasiados intentos. Inténtalo de nuevo en un minuto.", code="throttled")
        try:
            result = super().clean()
        except ValidationError:
            audit_auth_event("login_failed", channel="django_admin")
            raise
        if self.get_user() is not None:
            audit_auth_event("login_succeeded", channel="django_admin", actor_id=self.get_user().pk)
        return result


class ProtectedAdminSite(AdminSite):
    login_form = ProtectedAdminAuthenticationForm
