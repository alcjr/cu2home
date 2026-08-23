from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.conf import settings
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ===== Mis datos =====
    path('my-data/', views.my_data, name='my_data'),

    # ===== Favoritos =====
    path('favorites/', views.favorites_page, name='favorites'),
    path('favorites/data/', views.favorites_data, name='favorites_data'),
    path('favorites/<int:property_id>/toggle/', views.toggle_favorite, name='toggle_favorite'),

    # ===== Búsquedas guardadas =====
    path('saved-searches/', views.saved_search_list, name='saved_search_list'),
    path('saved-searches/create/', views.create_saved_search, name='create_saved_search'),
    path('saved-searches/<int:pk>/toggle/', views.toggle_saved_search, name='toggle_saved_search'),
    path('saved-searches/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),

    # ===== Mis alertas =====
    path('alerts/', views.alerts_page, name='alerts'),
    path('alerts/data/', views.alerts_data, name='alerts_data'),
    path('alerts/data/<int:pk>/', views.alerts_detail, name='alerts_detail'),

    # ===== Mis inmuebles =====
    path('my-properties/', views.my_properties, name='my_properties'),
    path('my-properties/data/', views.my_properties_data, name='my_properties_data'),
    path('my-properties/data/<int:pk>/', views.my_properties_detail, name='my_properties_detail'),
    path('my-properties/<int:pk>/images/', views.my_property_image_upload, name='my_property_image_upload'),
    path('my-properties/<int:pk>/images/<int:image_id>/', views.my_property_image_delete, name='my_property_image_delete'),
    path('my-properties/<int:pk>/images/<int:image_id>/cover/', views.my_property_image_set_cover, name='my_property_image_set_cover'),

    # ===== Recuperación de contraseña =====
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset_form.html',
            email_template_name='users/emails/password_reset_email.txt',
            subject_template_name='users/emails/password_reset_subject.txt',
            success_url=reverse_lazy('users:password_reset_done'),
            from_email=settings.DEFAULT_FROM_EMAIL,
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='users/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
            success_url=reverse_lazy('users:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='users/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # ===== Recuperación de usuario =====
    path('forgot-username/', views.forgot_username, name='forgot_username'),
]