from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/properties/', include('apps.properties.urls')),
    path('api/v1/projects/', include('apps.projects.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
]
