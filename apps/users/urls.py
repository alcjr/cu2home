from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('favorites/', views.favorite_list, name='favorites'),
    path('favorites/<int:property_id>/toggle/', views.toggle_favorite, name='toggle_favorite'),
    path('saved-searches/', views.saved_search_list, name='saved_search_list'),
    path('saved-searches/create/', views.create_saved_search, name='create_saved_search'),
    path('saved-searches/<int:pk>/toggle/', views.toggle_saved_search, name='toggle_saved_search'),
    path('saved-searches/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),
    path('my-properties/', views.my_properties, name='my_properties'),

    # ===== Recuperación de contraseña =====
    # Vistas built-in de Django (django.contrib.auth.views) -- solo se
    # personalizan template_name (para mantener el estilo del portal) y
    # los nombres de las plantillas de email. El flujo de 4 pasos es el
    # estándar de Django: form -> done (email enviado) -> confirm (desde
    # el link del email, con uidb64/token) -> complete.
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset_form.html',
            email_template_name='users/emails/password_reset_email.txt',
            subject_template_name='users/emails/password_reset_subject.txt',
            success_url=reverse_lazy('users:password_reset_done'),
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

    # ===== Recuperación de usuario ===== (no built-in en Django, ver views.py)
    path('forgot-username/', views.forgot_username, name='forgot_username'),
    # Añade aquí otras rutas que necesites
]
