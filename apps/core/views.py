from django.shortcuts import render
from django.db.models import Count

from apps.properties.models import Property
from apps.properties.constants import PROPERTY_TYPES


def index(request):
    """
    Página de inicio (portada) del portal cu2home.
    Muestra propiedades destacadas, provincias con conteo y formulario de búsqueda.
    """
    # Propiedades destacadas: las 6 más recientes
    featured_properties = Property.objects.filter(
        is_active=True
    ).order_by('-created_at')[:6]

    # Provincias con conteo de propiedades activas
    provinces_with_counts = (
        Property.objects.filter(is_active=True)
        .values('province')
        .annotate(count=Count('id'))
        .order_by('province')
    )

    # Para el select de provincias
    provinces_list = [p['province'] for p in provinces_with_counts if p['province']]

    # Municipios (puedes expandir esta lista con los municipios reales de Cuba)
    municipalities = [
        'Centro Habana', 'Playa', 'Vedado', 'Miramar',
        'Santa Clara', 'Trinidad', 'Santiago de Cuba',
        'Holguín', 'Varadero', 'Cienfuegos', 'Camagüey'
    ]

    context = {
        'featured_properties': featured_properties,
        'provinces': provinces_list,
        'provinces_with_counts': provinces_with_counts,
        'municipalities': municipalities,
        'property_types': PROPERTY_TYPES,
    }
    return render(request, 'core/index.html', context)