from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.property_list, name='list'),
    path('get-municipalities/', views.get_municipalities, name='get_municipalities'),
    path('results.json', views.property_results_json, name='results_json'),

    # === ACCIONES AJAX (DEBEN IR ANTES DE DETAIL) ===
    path('<int:pk>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('<int:pk>/increment-email-contact/', views.increment_email_contact, name='increment_email_contact'),
    path('<int:pk>/quick-view.json', views.property_detail_json, name='quick_view_json'),

    # === DETALLE (PATRÓN MÁS GENÉRICO, AL FINAL) ===
    path('<int:pk>/<slug:slug>/', views.property_detail, name='detail'),
]
