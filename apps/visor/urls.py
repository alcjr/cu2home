from django.urls import path
from . import views

app_name = 'visor'

urlpatterns = [
    path('', views.visor, name='visor'),
    path('api/', views.visor_api, name='api'),
    path('api/stats/', views.visor_stats_api, name='stats'),
    path('api/clear/', views.visor_clear, name='clear'),
    path('download/', views.visor_download, name='download'),
]
