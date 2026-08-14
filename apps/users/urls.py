from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('favorites/', views.favorite_list, name='favorite_list'),
    path('saved-searches/', views.saved_search_list, name='saved_search_list'),
    path('saved-searches/create/', views.create_saved_search, name='create_saved_search'),
    path('saved-searches/<int:pk>/toggle/', views.toggle_saved_search, name='toggle_saved_search'),
    path('saved-searches/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),
    # Añade aquí otras rutas que necesites
]