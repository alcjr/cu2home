from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def _is_superuser(user):
    """
    Solo superusuarios.
    - Anónimo -> False (user_passes_test redirige a LOGIN_URL).
    - Autenticado pero no superusuario -> 403 explícito, para no
      reenviarlo al login en bucle.
    """
    if not user.is_authenticated:
        return False
    if not user.is_superuser:
        raise PermissionDenied
    return True


superuser_required = user_passes_test(_is_superuser)