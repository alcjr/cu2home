from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),  # Esto ya incluye la vista index
    path('properties/', include('apps.properties.urls')),
    path('users/', include('apps.users.urls')),
    path('auth/', include('apps.authentication.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('panel/', views.panel, name='panel'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)