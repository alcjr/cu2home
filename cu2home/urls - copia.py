from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import index, panel  # <-- importar las vistas

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    path('', index, name='home'),          # <-- Ruta raíz -> portada
    path('panel/', panel, name='panel'),   # <-- Acceso personalizado al admin de Django
    path('', include('apps.properties.urls')),
    path('auth/', include('apps.authentication.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('visor/', include('apps.visor.urls')),
    path('config/', include('apps.config.urls')),
    path('users/', include('apps.users.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)