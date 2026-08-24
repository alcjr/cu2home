from django.urls import path
from . import views

app_name = 'config'

urlpatterns = [
    path('', views.config, name='config'),
    path('api/config/', views.config_api_get, name='api-get'),
    path('api/config/save/', views.config_api_save, name='api-save'),
    path('api/config/reload/', views.config_api_reload, name='api-reload'),
]
