from django.urls import path

from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.StaffLoginView.as_view(), name='login'),
    path('logout/', views.StaffLogoutView.as_view(), name='logout'),
]
