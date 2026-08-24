from django.urls import path
from django.conf import settings
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data, name='data'),
]

# Endpoint de diagnóstico solo en desarrollo
if getattr(settings, 'DEBUG', False):
    urlpatterns.append(
        path('test/', views.test_json, name='test')
    )
