from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ===== Favoritos =====
    # Un único patrón por vista/nombre (antes había duplicados: dos
    # 'favorites/' -- uno a la vieja favorite_list basada en tabla, otro
    # a favorites_page con la dxDataGrid, con el segundo inalcanzable
    # porque el primero coincidía antes -- y dos 'toggle_favorite' que
    # además apuntaban al mismo nombre de función pisado en views.py,
    # ver corrección ahí).
    path('favorites/', views.favorites_page, name='favorites'),
    path('favorites/data/', views.favorites_data, name='favorites_data'),
    path('favorites/<int:property_id>/toggle/', views.toggle_favorite, name='toggle_favorite'),

    path('saved-searches/', views.saved_search_list, name='saved_search_list'),
    path('saved-searches/create/', views.create_saved_search, name='create_saved_search'),
    path('saved-searches/<int:pk>/toggle/', views.toggle_saved_search, name='toggle_saved_search'),
    path('saved-searches/<int:pk>/delete/', views.delete_saved_search, name='delete_saved_search'),
    # ===== Mis inmuebles =====
    path('my-properties/', views.my_properties, name='my_properties'),
    # GET (listado) + POST (alta) -- load()/insert() del CustomStore
    path('my-properties/data/', views.my_properties_data, name='my_properties_data'),
    # PATCH (edición) + DELETE (borrado) -- update()/remove() del CustomStore
    path('my-properties/data/<int:pk>/', views.my_properties_detail, name='my_properties_detail'),
    # Imágenes: se gestionan aparte del CustomStore principal (ver views.py)
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
