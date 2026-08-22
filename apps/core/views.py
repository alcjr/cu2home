from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count, Q
from apps.properties.models import Property, Province, Municipality
from apps.properties.constants import PROPERTY_TYPES


def index(request):
    """Vista principal del portal"""
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

    # Contadores por tipo de oferta (para la sección de resultados)
    sale_count = Property.objects.filter(offer_type='sale', is_active=True).count()
    rent_count = Property.objects.filter(offer_type='rent', is_active=True).count()
    swap_count = Property.objects.filter(offer_type='swap', is_active=True).count()

    # Configuración de moneda (se puede mover a context_processors si se prefiere)
    from django.conf import settings
    
    context = {
        'featured_properties': featured,
        'provinces': provinces,
        'provinces_with_counts': provinces_with_counts,
        'municipalities': Municipality.objects.none(),  # Inicialmente vacío
        'property_types': PROPERTY_TYPES,
        # Contadores para la interfaz
        'sale_count': sale_count,
        'rent_count': rent_count,
        'swap_count': swap_count,
        # Configuración de moneda desde settings
        'currency_symbol': getattr(settings, 'CURRENCY_SYMBOL', '$'),
        'currency_decimal_places': getattr(settings, 'CURRENCY_DECIMAL_PLACES', 2),
        'currency_thousands_sep': getattr(settings, 'CURRENCY_THOUSANDS_SEP', '.'),
        'currency_decimal_sep': getattr(settings, 'CURRENCY_DECIMAL_SEP', ','),
        'currency_symbol_position': getattr(settings, 'CURRENCY_SYMBOL_POSITION', 'before_attached'),
        'site_name': getattr(settings, 'SITE_NAME', 'cu2home'),
    }
    return render(request, 'core/index.html', context)


def get_municipalities(request):
    """
    Vista para HTMX que devuelve los municipios de una provincia.
    Se usa en el select de municipios cuando cambia la provincia.
    """
    province_id = request.GET.get('province_id')
    if not province_id:
        return JsonResponse({'error': 'Provincia no especificada'}, status=400)
    
    try:
        municipalities = Municipality.objects.filter(province_id=province_id).order_by('name')
        return render(request, 'core/_municipality_options.html', {
            'municipalities': municipalities
        })
    except ValueError:
        return JsonResponse({'error': 'ID de provincia inválido'}, status=400)


def results_json(request):
    """
    Endpoint JSON para el grid de resultados.
    Soporta filtros por provincia, municipio, tipo de propiedad, precio y tipo de oferta.
    """
    # Obtener parámetros de filtro
    province_id = request.GET.get('province_id')
    municipality_id = request.GET.get('municipality_id')
    property_type = request.GET.get('property_type')
    max_price = request.GET.get('max_price')
    offer_type = request.GET.get('offer_type', 'sale')
    
    # Parámetros de paginación
    try:
        skip = int(request.GET.get('skip', 0))
        take = int(request.GET.get('take', 12))
    except ValueError:
        skip = 0
        take = 12

    # Construir queryset base
    queryset = Property.objects.filter(is_active=True)
    
    # Aplicar filtros
    if offer_type:
        queryset = queryset.filter(offer_type=offer_type)
    
    if province_id and province_id.isdigit():
        queryset = queryset.filter(province_id=int(province_id))
    
    if municipality_id and municipality_id.isdigit():
        queryset = queryset.filter(municipality_id=int(municipality_id))
    
    if property_type:
        queryset = queryset.filter(property_type=property_type)
    
    if max_price and max_price.replace('.', '').isdigit():
        queryset = queryset.filter(price__lte=float(max_price))

    # Contar total y obtener resultados paginados
    total_count = queryset.count()
    properties = queryset.select_related('province', 'municipality')[skip:skip + take]

    # Serializar datos
    data = []
    for prop in properties:
        data.append({
            'id': prop.id,
            'title': prop.title,
            'price': float(prop.price) if prop.price else None,
            'sale_price': float(prop.sale_price) if hasattr(prop, 'sale_price') and prop.sale_price else None,
            'rent_price': float(prop.rent_price) if hasattr(prop, 'rent_price') and prop.rent_price else None,
            'offer_type': prop.offer_type,
            'offer_type_display': prop.get_offer_type_display(),
            'property_type': prop.get_property_type_display() if prop.property_type else None,
            'city': prop.city,
            'province': prop.province.name if prop.province else None,
            'rooms': prop.rooms,
            'bathrooms': prop.bathrooms,
            'surface': prop.surface,
            'image_url': prop.get_cover_image_url() if hasattr(prop, 'get_cover_image_url') else None,
            'status': prop.status,
            'detail_url': prop.get_absolute_url() if hasattr(prop, 'get_absolute_url') else '#',
        })

    return JsonResponse({
        'data': data,
        'totalCount': total_count
    })


def quick_view_json(request, pk):
    """
    Endpoint JSON para la vista rápida de una propiedad.
    Devuelve todos los datos necesarios para el popup de quick view.
    """
    prop = get_object_or_404(Property, pk=pk, is_active=True)

    # Obtener imágenes
    images = []
    if hasattr(prop, 'images'):
        for img in prop.images.all():
            images.append({
                'url': img.image.url if hasattr(img, 'image') and img.image else '',
                'is_cover': img.is_cover if hasattr(img, 'is_cover') else False,
            })

    # Preparar datos del agente
    agent_data = None
    if hasattr(prop, 'agent') and prop.agent:
        agent = prop.agent
        agent_data = {
            'name': agent.name if hasattr(agent, 'name') else None,
            'email': agent.email if hasattr(agent, 'email') else None,
            'phone': agent.phone if hasattr(agent, 'phone') else None,
            'bio': agent.bio if hasattr(agent, 'bio') else None,
            'avatar_url': agent.avatar.url if hasattr(agent, 'avatar') and agent.avatar else None,
            'user_type_display': agent.get_user_type_display() if hasattr(agent, 'get_user_type_display') else None,
            'agency_name': agent.agency_name if hasattr(agent, 'agency_name') else None,
        }

    # Construir respuesta
    data = {
        'id': prop.id,
        'title': prop.title,
        'price': float(prop.price) if prop.price else None,
        'display_price': prop.get_display_price() if hasattr(prop, 'get_display_price') else str(prop.price),
        'description': prop.description,
        'address': prop.address,
        'city': prop.city,
        'municipality': prop.municipality.name if prop.municipality else None,
        'province': prop.province.name if prop.province else None,
        # Coordenadas para el mapa
        'municipality_latitude': float(prop.municipality.latitude) if prop.municipality and hasattr(prop.municipality, 'latitude') and prop.municipality.latitude else None,
        'municipality_longitude': float(prop.municipality.longitude) if prop.municipality and hasattr(prop.municipality, 'longitude') and prop.municipality.longitude else None,
        'property_type': prop.get_property_type_display() if prop.property_type else None,
        'rooms': prop.rooms,
        'bathrooms': prop.bathrooms,
        'surface': prop.surface,
        'views_count': prop.views_count if hasattr(prop, 'views_count') else 0,
        'status': prop.status,
        'offer_type': prop.offer_type,
        'images': images,
        # Amenidades
        'has_elevator': prop.has_elevator if hasattr(prop, 'has_elevator') else False,
        'has_heating': prop.has_heating if hasattr(prop, 'has_heating') else False,
        'has_air_conditioning': prop.has_air_conditioning if hasattr(prop, 'has_air_conditioning') else False,
        # Agente
        'agent': agent_data,
        'detail_url': prop.get_absolute_url() if hasattr(prop, 'get_absolute_url') else '#',
    }

    return JsonResponse(data)


def property_list(request):
    """
    Vista para la lista de propiedades.
    Muestra todas las propiedades activas con paginación.
    """
    properties = Property.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'properties': properties,
        'property_types': PROPERTY_TYPES,
    }
    return render(request, 'properties/list.html', context)