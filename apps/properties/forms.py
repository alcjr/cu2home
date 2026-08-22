from django import forms
from django.utils.translation import gettext_lazy as _
from parler.forms import TranslatableModelForm
from .models import Property, Province, Municipality, PropertyOfferType
from .constants import PROPERTY_TYPES


class PropertyForm(TranslatableModelForm):
    """Formulario para crear/editar propiedades"""

    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'offer_type',
            'sale_price', 'rent_price', 'seasonal_rent_price', 'deposit_amount',
            # 'city' ELIMINADO - Ya no existe en el modelo
            'postal_code', 'province', 'municipality', 'address',
            'surface', 'rooms', 'bathrooms',
            'has_elevator', 'has_heating', 'has_air_conditioning',
            'status', 'is_active',
            # 'agent' ELIMINADO A PROPÓSITO: si se deja como campo del
            # form, un PATCH manual a users:my_properties_detail (fuera
            # del grid, que nunca lo envía) podría reasignar el
            # inmueble a otro agente, porque esa vista no fuerza
            # obj.agent = request.user tras form.save() como sí hace la
            # de alta (my_properties_data). El dueño real de un
            # Property siempre lo decide la vista a partir de
            # request.user, nunca el propio formulario.
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código postal'}),
        }
        labels = {
            'title': _('Título'),
            'description': _('Descripción'),
            'property_type': _('Tipo de propiedad'),
            'offer_type': _('Tipo de oferta'),
            'sale_price': _('Precio de venta'),
            'rent_price': _('Precio de alquiler (mensual)'),
            'seasonal_rent_price': _('Precio de alquiler temporal (diario)'),
            'deposit_amount': _('Depósito'),
            'postal_code': _('Código postal'),
            'province': _('Provincia'),
            'municipality': _('Municipio'),
            'address': _('Dirección'),
            'surface': _('Superficie (m²)'),
            'rooms': _('Habitaciones'),
            'bathrooms': _('Baños'),
            'has_elevator': _('Ascensor'),
            'has_heating': _('Calefacción'),
            'has_air_conditioning': _('Aire acondicionado'),
            'status': _('Estado'),
            'is_active': _('Activo'),
        }
        help_texts = {
            'sale_price': _('Requerido si la propiedad está en venta'),
            'rent_price': _('Requerido si la propiedad está en alquiler'),
            'seasonal_rent_price': _('Precio por día para alquileres temporales'),
            'deposit_amount': _('Depósito de garantía para alquileres'),
            'postal_code': _('Código postal donde se ubica la propiedad'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Hacer que los campos obligatorios sean requeridos
        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['property_type'].required = True
        self.fields['offer_type'].required = True

        # Configurar selectores
        self.fields['property_type'].choices = [('', '---')] + list(PROPERTY_TYPES)
        self.fields['offer_type'].choices = [('', '---')] + list(PropertyOfferType.choices)

        # Filtrar municipios si ya hay provincia seleccionada
        if self.instance and self.instance.province_id:
            self.fields['municipality'].queryset = Municipality.objects.filter(
                province_id=self.instance.province_id
            )

    def clean(self):
        """Validación personalizada del formulario"""
        cleaned_data = super().clean()
        offer_type = cleaned_data.get('offer_type')
        sale_price = cleaned_data.get('sale_price')
        rent_price = cleaned_data.get('rent_price')

        if offer_type in ['sale', 'sale_or_rent'] and not sale_price:
            self.add_error('sale_price', _('El precio de venta es obligatorio para ofertas de venta.'))

        if offer_type in ['rent', 'sale_or_rent'] and not rent_price:
            self.add_error('rent_price', _('El precio de alquiler es obligatorio para ofertas de alquiler.'))

        return cleaned_data


class PropertyFilterForm(forms.Form):
    """Formulario para filtrar propiedades en el listado"""

    q = forms.CharField(
        required=False,
        label=_('Buscar'),
        widget=forms.TextInput(attrs={'placeholder': _('Buscar por título o descripción...')})
    )

    province_id = forms.ModelChoiceField(
        queryset=Province.objects.all(),
        required=False,
        label=_('Provincia'),
        empty_label=_('Todas las provincias'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    municipality_id = forms.ModelChoiceField(
        queryset=Municipality.objects.all(),
        required=False,
        label=_('Municipio'),
        empty_label=_('Todos los municipios'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    offer_type = forms.ChoiceField(
        choices=[('', _('Todos los tipos'))] + list(PropertyOfferType.choices),
        required=False,
        label=_('Tipo de oferta'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    property_type = forms.ChoiceField(
        choices=[('', _('Todos los tipos'))] + list(PROPERTY_TYPES),
        required=False,
        label=_('Tipo de propiedad'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Filtros de precio (venta)
    min_sale_price = forms.DecimalField(
        required=False,
        label=_('Precio mínimo (venta)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo'})
    )
    max_sale_price = forms.DecimalField(
        required=False,
        label=_('Precio máximo (venta)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Máximo'})
    )

    # Filtros de precio (alquiler)
    min_rent_price = forms.DecimalField(
        required=False,
        label=_('Precio mínimo (alquiler)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo'})
    )
    max_rent_price = forms.DecimalField(
        required=False,
        label=_('Precio máximo (alquiler)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Máximo'})
    )

    # Precio máximo (filtro rápido)
    max_price = forms.DecimalField(
        required=False,
        label=_('Precio máximo'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Máximo'})
    )

    # Superficie
    min_surface = forms.IntegerField(
        required=False,
        label=_('Superficie mínima (m²)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo'})
    )
    max_surface = forms.IntegerField(
        required=False,
        label=_('Superficie máxima (m²)'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Máximo'})
    )

    # Características
    rooms = forms.IntegerField(
        required=False,
        label=_('Habitaciones mínimas'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo'})
    )

    bathrooms = forms.IntegerField(
        required=False,
        label=_('Baños mínimos'),
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo'})
    )

    has_elevator = forms.BooleanField(
        required=False,
        label=_('Ascensor'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    has_heating = forms.BooleanField(
        required=False,
        label=_('Calefacción'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    has_air_conditioning = forms.BooleanField(
        required=False,
        label=_('Aire acondicionado'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Agregar clases CSS para estilos consistentes
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
                field.widget.attrs['class'] = field.widget.attrs['class'].strip()
