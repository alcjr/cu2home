from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

# Importaciones corregidas
from apps.properties.models import SavedSearch
from .forms import ForgotUsernameForm, RegisterForm, SaveSearchForm

User = get_user_model()


def _auth_view(request, active_tab):
    """
    Página combinada de acceso al portal público: dos pestañas
    (Iniciar sesión / Crear cuenta) sobre la misma URL/plantilla, igual
    que el patrón de pestañas del hero (Comprar/Alquilar/Permutar en
    index.html). El botón "Registro" del header apunta aquí -- si el
    visitante ya tiene cuenta, cambia de pestaña e inicia sesión sin
    salir de la página; si no la tiene, se registra.

    NO tiene relación con apps/authentication (ese es el login de
    staff para el panel admin, con su propio StaffLoginForm que exige
    is_staff). Este es el login del portal público, para
    compradores/agentes.

    active_tab: 'login' o 'register' -- cuál pestaña se muestra activa
    al cargar la página (viene de qué URL entró el usuario:
    users:login o users:register). Si el POST es de la otra pestaña,
    se reactiva esa para mostrar los errores en el formulario correcto.
    """
    if request.user.is_authenticated:
        return redirect('properties:list')

    login_form = AuthenticationForm(request)
    register_form = RegisterForm()

    if request.method == 'POST':
        submitted_form = request.POST.get('form')

        if submitted_form == 'login':
            active_tab = 'login'
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                auth_login(request, login_form.get_user())
                messages.success(request, _('Welcome back!'))
                return redirect('properties:list')

        elif submitted_form == 'register':
            active_tab = 'register'
            register_form = RegisterForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                auth_login(request, user)
                messages.success(request, _('Welcome to cu2home! Your account has been created.'))
                return redirect('properties:list')

    return render(request, 'users/auth.html', {
        'login_form': login_form,
        'register_form': register_form,
        'active_tab': active_tab,
    })


def register(request):
    return _auth_view(request, active_tab='register')


def login_view(request):
    return _auth_view(request, active_tab='login')


@require_POST
def logout_view(request):
    """
    Logout vía POST (no GET) -- así evitamos que el logout se dispare por
    accidente desde un link, prefetch del navegador, o crawler, y de paso
    cumplimos con lo que Django >=4.1 exige por defecto en LogoutView.
    El botón "Cerrar sesión" del dropdown del header envía este form.
    """
    auth_logout(request)
    messages.success(request, _('You have been logged out.'))
    return redirect('properties:list')


@login_required(login_url='users:login')
def favorite_list(request):
    """
    Muestra la lista de favoritos del usuario actual.
    """
    # Aquí se debe obtener la lista de propiedades favoritas del usuario.
    # Por ahora, devolvemos un template con un mensaje.
    return render(request, 'users/favorites.html', {
        'title': _('Mis favoritos'),
        'favorites': [],  # Reemplazar con la lógica real
    })


@login_required(login_url='users:login')
def my_properties(request):
    """
    Placeholder de "Mis inmuebles" (alta/gestión de propiedades del
    usuario-agente). El flujo de creación de Property (con imágenes,
    ubicación, etc.) todavía no está implementado -- esta vista solo
    deja el enlace del header funcionando mientras se construye esa
    parte en un paso posterior.
    """
    return render(request, 'users/my_properties.html', {
        'title': _('Mis inmuebles'),
        'properties': request.user.properties.all() if hasattr(request.user, 'properties') else [],
    })


@login_required(login_url='users:login')
def saved_search_list(request):
    searches = SavedSearch.objects.filter(user=request.user)
    return render(request, 'users/saved_searches.html', {'searches': searches})


@login_required(login_url='users:login')
def create_saved_search(request):
    if request.method == 'POST':
        form = SaveSearchForm(request.POST)
        if form.is_valid():
            search = form.save(commit=False)
            search.user = request.user
            search.save()
            messages.success(request, _('Search saved successfully.'))
            return redirect('users:saved_search_list')
    else:
        form = SaveSearchForm()
    return render(request, 'users/create_saved_search.html', {'form': form})


@login_required(login_url='users:login')
@require_POST
def delete_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.delete()
    messages.success(request, _('Search deleted.'))
    return redirect('users:saved_search_list')


@login_required(login_url='users:login')
@require_POST
def toggle_saved_search(request, pk):
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    search.is_active = not search.is_active
    search.save()
    status = _('activated') if search.is_active else _('deactivated')
    messages.success(request, f'Search {status}.')
    return redirect('users:saved_search_list')


def forgot_username(request):
    """
    'Olvidé mi usuario', complementario a PasswordResetView (que ya trae
    Django de serie para la contraseña -- ver urls.py). No es una vista
    de Django, porque no existe equivalente built-in para recuperar el
    *username*.

    A propósito SIEMPRE renderiza el mismo template de confirmación tras
    un POST válido, exista o no ese email en la base de datos, y con
    fail_silently=True en el envío -- así este formulario no sirve para
    enumerar qué correos están registrados en el portal (mismo motivo
    por el que PasswordResetView de Django se comporta igual).
    """
    if request.method == 'POST':
        form = ForgotUsernameForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            matching_users = User.objects.filter(email__iexact=email)
            if matching_users.exists():
                usernames = ', '.join(sorted(u.username for u in matching_users))
                send_mail(
                    subject=_('Your cu2home username'),
                    message=render_to_string('users/emails/forgot_username_email.txt', {
                        'usernames': usernames,
                    }),
                    from_email=None,  # usa settings.DEFAULT_FROM_EMAIL
                    recipient_list=[email],
                    fail_silently=True,
                )
            return render(request, 'users/forgot_username_done.html')
    else:
        form = ForgotUsernameForm()

    return render(request, 'users/forgot_username.html', {'form': form})
