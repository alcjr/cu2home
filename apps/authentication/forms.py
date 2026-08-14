from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _


class StaffLoginForm(AuthenticationForm):
    """
    AuthenticationForm estándar de Django + comprobación de is_staff.
    La validación de credenciales (usuario/contraseña, cuenta activa,
    bloqueos, etc.) la sigue haciendo Django; aquí solo se añade el
    requisito extra de que la cuenta tenga acceso al panel.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        'not_staff': _('This account does not have access to the admin panel.'),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                self.error_messages['not_staff'],
                code='not_staff',
            )
