from django.shortcuts import render
from django.db.models import Count
from apps.properties.models import Property, Province, Municipality
from apps.properties.constants import PROPERTY_TYPES


def index(request):
    featured = Property.objects.filter(is_active=True).order_by('-created_at')[:6]
    provinces = Province.objects.all().order_by('name')

    # Conteo de propiedades por provincia (para la sección de provincias)
    provinces_with_counts = []
    for province in provinces:
        count = Property.objects.filter(province=province, is_active=True).count()
        provinces_with_counts.append({
            'name': province.name,
            'count': count,
            'icon': 'fa-city',
        })

    context = {
        'featured_properties': featured,
        'provinces': provinces,
        'provinces_with_counts': provinces_with_counts,
        'municipalities': Municipality.objects.none(),  # Inicialmente vacío
        'property_types': PROPERTY_TYPES,
    }
    return render(request, 'core/index.html', context)