from django.contrib.auth import views as auth_views

from .forms import StaffLoginForm


class StaffLoginView(auth_views.LoginView):
    """
    Login del panel admin. Reutiliza LoginView de Django (maneja CSRF,
    redirect-after-login vía ?next=, throttling básico de sesión, etc.)
    en vez de reimplementar ese flujo a mano.
    """
    template_name = 'authentication/login.html'
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True


class StaffLogoutView(auth_views.LogoutView):
    """Logout estándar de Django; redirige según LOGOUT_REDIRECT_URL."""
    pass
