from django import forms
from django.utils.translation import gettext_lazy as _

from .constants import PROPERTY_TYPES
from .models import Municipality, Province, PropertyOfferType


class PropertyFilterForm(forms.Form):
    # === BÚSQUEDA GENERAL ===
    q = forms.CharField(required=False, label=_('Search'), max_length=200, help_text=_('Title or description'))
    city = forms.CharField(required=False, label=_('City'), max_length=100)

    # === UBICACIÓN ===
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

    # === OFERTA ===
    offer_type = forms.ChoiceField(
        required=False,
        label=_('Offer type'),
        choices=[('', _('All'))] + [
            ('sale', _('Sale')),
            ('rent', _('Rent')),
            ('swap', _('Swap')),
        ],
    )

    # === PRECIO MÁXIMO (filtro rápido del home) ===
    max_price = forms.DecimalField(
        required=False,
        label=_('Max price'),
        decimal_places=2,
        max_digits=12,
        min_value=0,
    )

    # === PRECIOS DE VENTA ===
    min_sale_price = forms.DecimalField(
        required=False, 
        label=_('Min sale price'), 
        decimal_places=2, 
        max_digits=12, 
        min_value=0
    )
    max_sale_price = forms.DecimalField(
        required=False, 
        label=_('Max sale price'), 
        decimal_places=2, 
        max_digits=12, 
        min_value=0
    )

    # === PRECIOS DE ALQUILER ===
    min_rent_price = forms.DecimalField(
        required=False, 
        label=_('Min rent price'), 
        decimal_places=2, 
        max_digits=12, 
        min_value=0
    )
    max_rent_price = forms.DecimalField(
        required=False, 
        label=_('Max rent price'), 
        decimal_places=2, 
        max_digits=12, 
        min_value=0
    )

    # === CARACTERÍSTICAS ===
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
        
        # Validar precios de venta
        min_sale = cleaned_data.get('min_sale_price')
        max_sale = cleaned_data.get('max_sale_price')
        if min_sale is not None and max_sale is not None and min_sale > max_sale:
            self.add_error('max_sale_price', _('Max sale price must be greater than or equal to min sale price.'))
        
        # Validar precios de alquiler
        min_rent = cleaned_data.get('min_rent_price')
        max_rent = cleaned_data.get('max_rent_price')
        if min_rent is not None and max_rent is not None and min_rent > max_rent:
            self.add_error('max_rent_price', _('Max rent price must be greater than or equal to min rent price.'))
        
        # Validar superficie
        min_surface = cleaned_data.get('min_surface')
        max_surface = cleaned_data.get('max_surface')
        if min_surface is not None and max_surface is not None and min_surface > max_surface:
            self.add_error('max_surface', _('Max surface must be greater than or equal to min surface.'))
        
        return cleaned_data