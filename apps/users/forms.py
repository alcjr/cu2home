from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from apps.properties.constants import PROPERTY_TYPES, DEFAULT_FAVORITE_LIST_NAME
from apps.properties.models import SavedSearch

User = get_user_model()


class RegisterForm(UserCreationForm):
    """
    Registro del portal público. Extiende UserCreationForm (usuario +
    contraseña con validación estándar de Django) añadiendo email
    obligatorio y único, y nombre/apellidos opcionales. El UserProfile
    se crea solo, vía la señal post_save de apps/users/signals.py --
    este form no necesita tocar UserProfile para nada.
    """
    email = forms.EmailField(required=True, label=_('Email'))
    first_name = forms.CharField(max_length=150, required=False, label=_('First name'))
    last_name = forms.CharField(max_length=150, required=False, label=_('Last name'))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('A user with that email already exists.'))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class SaveSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ['name', 'frequency', 'query_params']
        widgets = {
            'query_params': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.name:
            self.fields['name'].initial = DEFAULT_FAVORITE_LIST_NAME


class FavoriteListForm(forms.Form):
    name = forms.CharField(max_length=100, required=True, label=_('List name'))
    # Puedes agregar más campos según tu lógica


class ForgotUsernameForm(forms.Form):
    """
    Formulario de 'olvidé mi usuario'. A propósito NO valida si el email
    existe en clean_email() (a diferencia de RegisterForm.clean_email) --
    la vista siempre responde con el mismo mensaje genérico exista o no
    ese email, para no dejar enumerar cuentas registradas a través de
    este formulario.
    """
    email = forms.EmailField(required=True, label=_('Email'))
