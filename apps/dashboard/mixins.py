from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class StaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin para restringir el acceso solo a usuarios staff (is_staff=True).
    """
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        raise PermissionDenied("No tienes permisos para acceder a esta sección.")