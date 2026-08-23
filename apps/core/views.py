from django.conf import settings
from django.shortcuts import render

from apps.core.decorators import superuser_required
from apps.properties.constants import PROPERTY_TYPES
from apps.properties.models import Municipality, Property, Province


def index(request):
    """Vista principal del portal"""
    featured = Property.objects.filter(is_active=True).order_by('-created_at')[:6]
    provinces = Province.objects.all().order_by('name')

    provinces_with_counts = []
    for province in provinces:
        count = Property.objects.filter(province=province, is_active=True).count()
        provinces_with_counts.append({
            'name': province.name,
            'count': count,
            'icon': 'fa-city',
        })

    sale_count = Property.objects.filter(offer_type='sale', is_active=True).count()
    rent_count = Property.objects.filter(offer_type='rent', is_active=True).count()
    swap_count = Property.objects.filter(offer_type='swap', is_active=True).count()

    context = {
        'featured_properties': featured,
        'provinces': provinces,
        'provinces_with_counts': provinces_with_counts,
        'municipalities': Municipality.objects.none(),
        'property_types': PROPERTY_TYPES,
        'sale_count': sale_count,
        'rent_count': rent_count,
        'swap_count': swap_count,
        'currency_symbol': getattr(settings, 'CURRENCY_SYMBOL', '$'),
        'currency_decimal_places': getattr(settings, 'CURRENCY_DECIMAL_PLACES', 2),
        'currency_thousands_sep': getattr(settings, 'CURRENCY_THOUSANDS_SEP', '.'),
        'currency_decimal_sep': getattr(settings, 'CURRENCY_DECIMAL_SEP', ','),
        'currency_symbol_position': getattr(settings, 'CURRENCY_SYMBOL_POSITION', 'before_attached'),
        'site_name': getattr(settings, 'SITE_NAME', 'cu2home'),
    }
    return render(request, 'core/index.html', context)


@superuser_required
def panel(request):
    """Acceso personalizado al admin nativo de Django (solo superusuarios)"""
    return render(request, 'core/panel.html', {})