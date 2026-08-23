from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data, name='data'),
    path('test/', views.test_json, name='test'),  # ← Para diagnóstico
]