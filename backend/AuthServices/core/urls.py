"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


from users.ai_integrations import (
    GroqCredentialsView,
    GroqModelsView,
    GroqSettingsView,
    GroqTestConnectionView,
)
from users.audit_logs import AuditLogListView
from users.cookie_session import (
    CookieSessionLoginView,
    CookieSessionLogoutView,
    CookieSessionRefreshView,
)
from users.ollama_integrations import (
    ActiveAIProviderView,
    OllamaModelsView,
    OllamaPullStatusView,
    OllamaPullView,
    OllamaSettingsView,
    OllamaTestConnectionView,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/users/session/login/', CookieSessionLoginView.as_view(), name='cookie_session_login'),
    path('api/users/session/refresh/', CookieSessionRefreshView.as_view(), name='cookie_session_refresh'),
    path('api/users/session/logout/', CookieSessionLogoutView.as_view(), name='cookie_session_logout'),
    path('api/audit-logs/', AuditLogListView.as_view(), name='audit_logs_list'),
    path('api/integrations/ai/provider/', ActiveAIProviderView.as_view(), name='ai_active_provider'),
    path('api/integrations/groq/', GroqSettingsView.as_view(), name='groq_settings'),
    path('api/integrations/groq/credentials/', GroqCredentialsView.as_view(), name='groq_credentials'),
    path('api/integrations/groq/models/', GroqModelsView.as_view(), name='groq_models'),
    path('api/integrations/groq/test/', GroqTestConnectionView.as_view(), name='groq_test'),
    path('api/integrations/ollama/', OllamaSettingsView.as_view(), name='ollama_settings'),
    path('api/integrations/ollama/models/', OllamaModelsView.as_view(), name='ollama_models'),
    path('api/integrations/ollama/pull/', OllamaPullView.as_view(), name='ollama_pull'),
    path('api/integrations/ollama/pull/status/', OllamaPullStatusView.as_view(), name='ollama_pull_status'),
    path('api/integrations/ollama/test/', OllamaTestConnectionView.as_view(), name='ollama_test'),
    path('docs/', include('core.openapi')),
    path('docs/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
    path('', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
]
