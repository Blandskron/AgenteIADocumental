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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/integrations/groq/', GroqSettingsView.as_view(), name='groq_settings'),
    path('api/integrations/groq/credentials/', GroqCredentialsView.as_view(), name='groq_credentials'),
    path('api/integrations/groq/models/', GroqModelsView.as_view(), name='groq_models'),
    path('api/integrations/groq/test/', GroqTestConnectionView.as_view(), name='groq_test'),
    path('docs/', include('core.openapi')),
    path('docs/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
    path('', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
]
