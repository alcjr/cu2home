from django.urls import path
from . import views

app_name = 'visor'

urlpatterns = [
    path('', views.visor, name='visor'),
]