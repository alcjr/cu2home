from django import forms
from django.utils.translation import gettext_lazy as _

from .constants import PROPERTY_TYPES
from .models import Municipality, Province


class PropertyFilterForm(forms.Form):
    city = forms.CharField(required=False, label=_('City'), max_length=100)

    # Los nombres de campo coinciden a propósito con los <select name="province_id">
    # y <select name="municipality_id"> del buscador en core/index.html.
    province_id = forms.ModelChoiceField(
        required=False,
        label=_('Province'),
        queryset=Province.objects.all(),
        empty_label=_('All'),
    )
    municipality_id = forms.ModelChoiceField(
        required=False,
        label=_('Municipality'),
        queryset=Municipality.objects.all(),
        empty_label=_('All'),
    )

    min_price = forms.DecimalField(required=False, label=_('Min price'), decimal_places=2, max_digits=12, min_value=0)
    max_price = forms.DecimalField(required=False, label=_('Max price'), decimal_places=2, max_digits=12, min_value=0)

    min_surface = forms.IntegerField(required=False, label=_('Min surface (m²)'), min_value=0)
    max_surface = forms.IntegerField(required=False, label=_('Max surface (m²)'), min_value=0)

    rooms = forms.IntegerField(required=False, label=_('Min rooms'), min_value=0)
    bathrooms = forms.IntegerField(required=False, label=_('Min bathrooms'), min_value=0)

    property_type = forms.ChoiceField(
        required=False,
        label=_('Property type'),
        choices=[('', _('All'))] + PROPERTY_TYPES,
    )

    has_elevator = forms.BooleanField(required=False, label=_('Elevator'))
    has_heating = forms.BooleanField(required=False, label=_('Heating'))
    has_air_conditioning = forms.BooleanField(required=False, label=_('Air conditioning'))

    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            self.add_error('max_price', _('Max price must be greater than or equal to min price.'))
        min_surface = cleaned_data.get('min_surface')
        max_surface = cleaned_data.get('max_surface')
        if min_surface is not None and max_surface is not None and min_surface > max_surface:
            self.add_error('max_surface', _('Max surface must be greater than or equal to min surface.'))
        return cleaned_data