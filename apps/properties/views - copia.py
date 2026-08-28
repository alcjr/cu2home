from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import F, Q
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.utils.translation import gettext_lazy as _

from .forms import PropertyFilterForm
from .models import Property, Province, Municipality, PropertyOfferType

from .constants import PROPERTY_TYPES


ALLOWED_SORT = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'price': 'sale_price',
    '-price': '-sale_price',
    'surface': 'surface',
    '-surface': '-surface',
    'views_count': 'views_count',
    '-views_count': '-views_count',
}


def _filtered_properties(request):
    properties = Property.objects.filter(is_active=True).select_related(
        'province', 'municipality'
    ).prefetch_related('images')

    form = PropertyFilterForm(request.GET or None)
    selected_province = None

    if form.is_valid():
        data = form.cleaned_data
        selected_province = data.get('province_id')

        # === BÚSQUEDA POR TEXTO ===
        if data.get('q'):
            q = data['q']
            properties = properties.filter(
                Q(translations__title__icontains=q) |
                Q(translations__description__icontains=q)
            ).distinct()

        # === UBICACIÓN ===
        if data.get('province_id'):
            properties = properties.filter(province=data['province_id'])
        if data.get('municipality_id'):
            properties = properties.filter(municipality=data['municipality_id'])

        # === OFERTA ===
        offer_type = data.get('offer_type')
        if offer_type:
            if offer_type == 'sale':
                properties = properties.filter(
                    Q(offer_type='sale') | Q(offer_type='sale_or_rent')
                )
            elif offer_type == 'rent':
                properties = properties.filter(
                    Q(offer_type='rent') | Q(offer_type='sale_or_rent')
                )
            else:
                properties = properties.filter(offer_type=offer_type)

        # === PRECIO MÁXIMO (filtro rápido del buscador del home) ===
        if data.get('max_price') is not None:
            max_price = data['max_price']
            current_offer_type = data.get('offer_type')
            
            if current_offer_type == 'sale':
                properties = properties.filter(sale_price__lte=max_price)
            elif current_offer_type == 'rent':
                properties = properties.filter(rent_price__lte=max_price)
            elif current_offer_type == 'swap':
                # Para permuta no aplica filtro de precio
                pass
            else:
                # Si no hay oferta específica, filtrar cualquiera
                properties = properties.filter(
                    Q(sale_price__lte=max_price) | Q(rent_price__lte=max_price)
                )

        # === PRECIOS DE VENTA ===
        if data.get('min_sale_price') is not None:
            properties = properties.filter(sale_price__gte=data['min_sale_price'])
        if data.get('max_sale_price') is not None:
            properties = properties.filter(sale_price__lte=data['max_sale_price'])

        # === PRECIOS DE ALQUILER ===
        if data.get('min_rent_price') is not None:
            properties = properties.filter(rent_price__gte=data['min_rent_price'])
        if data.get('max_rent_price') is not None:
            properties = properties.filter(rent_price__lte=data['max_rent_price'])

        # === SUPERFICIE ===
        if data.get('min_surface') is not None:
            properties = properties.filter(surface__gte=data['min_surface'])
        if data.get('max_surface') is not None:
            properties = properties.filter(surface__lte=data['max_surface'])

        # === CARACTERÍSTICAS ===
        if data.get('rooms') is not None:
            properties = properties.filter(rooms__gte=data['rooms'])
        if data.get('bathrooms') is not None:
            properties = properties.filter(bathrooms__gte=data['bathrooms'])
        if data.get('property_type'):
            properties = properties.filter(property_type=data['property_type'])
        if data.get('has_elevator'):
            properties = properties.filter(has_elevator=True)
        if data.get('has_heating'):
            properties = properties.filter(has_heating=True)
        if data.get('has_air_conditioning'):
            properties = properties.filter(has_air_conditioning=True)

    sort_param = request.GET.get('sort', '-created_at')
    sort = ALLOWED_SORT.get(sort_param, '-created_at')
    properties = properties.order_by(sort)

    return properties, form, selected_province, sort_param


def property_list(request):
    properties, form, selected_province, sort_param = _filtered_properties(request)

    paginator = Paginator(properties, settings.SEARCH_RESULTS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    querystring_params = request.GET.copy()
    querystring_params.pop('page', None)
    querystring = querystring_params.urlencode()

    context = {
        'properties': page_obj,
        'form': form,
        'current_sort': sort_param if sort_param in ALLOWED_SORT else '-created_at',
        'selected_province': selected_province,
        'querystring': querystring,
    }

    if request.htmx:
        return render(request, 'properties/partials/list_results.html', context)

    return render(request, 'properties/list.html', context)


def property_detail(request, pk, slug):
    obj = get_object_or_404(
        Property.objects.select_related(
            'province', 'municipality', 'agent', 'agent__profile'
        ).prefetch_related('images'),
        pk=pk,
        is_active=True,
    )
    Property.objects.filter(pk=obj.pk).update(views_count=F('views_count') + 1)
    obj.refresh_from_db(fields=['views_count'])

    # property.images.all() ya viene precargado por prefetch_related, así
    # que esto no dispara una consulta adicional. Se antepone la portada
    # (is_cover) al resto, independientemente de su 'order': así la
    # imagen grande de la galería, la miniatura marcada como activa por
    # defecto y el bloque de fotos de la maqueta de impresión son siempre
    # coherentes entre sí, aunque alguien cambie la portada desde el
    # admin sin reordenar las imágenes.
    property_images = list(obj.images.all())
    cover_image = obj.cover_image
    if cover_image and property_images and property_images[0] != cover_image:
        property_images.remove(cover_image)
        property_images.insert(0, cover_image)

    return render(request, 'properties/detail.html', {
        'property': obj,
        'property_images': property_images,
        'cover_image': cover_image,
    })


def _serialize_property_for_grid(obj, request):
    cover = obj.cover_image

    if cover:
        image_url = request.build_absolute_uri(cover.image.url)
    else:
        # Sin fotos reales todavía: no inventamos una imagen de stock
        # externa (picsum.photos) que el usuario nunca subió y que el
        # frontend acababa mostrando como si fuera la portada real del
        # inmueble. Se manda None y es el frontend quien decide cómo
        # representar "sin foto" (ver buildResultCard en index.html).
        image_url = None

    # Determinar qué precio mostrar según la oferta
    if obj.offer_type == PropertyOfferType.SALE:
        price = float(obj.sale_price) if obj.sale_price else None
        price_label = _('Sale')
    elif obj.offer_type == PropertyOfferType.RENT:
        price = float(obj.rent_price) if obj.rent_price else None
        price_label = _('Rent / month')
    elif obj.offer_type == PropertyOfferType.SALE_OR_RENT:
        price = {
            'sale': float(obj.sale_price) if obj.sale_price else None,
            'rent': float(obj.rent_price) if obj.rent_price else None,
        }
        price_label = _('Sale / Rent')
    else:
        price = float(obj.sale_price) if obj.sale_price else None
        price_label = ''

    return {
        'id': obj.pk,
        'title': obj.safe_translation_getter('title', any_language=True) or '',
        'image_url': image_url,
        'price': price,
        'price_label': price_label,
        'sale_price': float(obj.sale_price) if obj.sale_price else None,
        'rent_price': float(obj.rent_price) if obj.rent_price else None,
        'offer_type': obj.offer_type,
        'offer_type_display': obj.get_offer_type_display(),
        'province': obj.province.name if obj.province else '',
        'municipality': obj.municipality.name if obj.municipality else '',
        'property_type': obj.get_property_type_display(),
        'rooms': obj.rooms,
        'bathrooms': obj.bathrooms,
        'surface': obj.surface,
        'status': obj.get_status_display(),
        'detail_url': reverse('properties:detail', args=[obj.pk, obj.slug]),
    }


@require_GET
def property_results_json(request):
    properties, _form, _selected_province, _sort_param = _filtered_properties(request)

    try:
        skip = int(request.GET.get('skip', 0))
    except (TypeError, ValueError):
        skip = 0
    skip = max(skip, 0)

    try:
        take = int(request.GET.get('take', 12))
    except (TypeError, ValueError):
        take = 12
    take = max(min(take, 50), 1)

    total_count = properties.count()
    page = properties[skip:skip + take]

    data = [_serialize_property_for_grid(obj, request) for obj in page]

    return JsonResponse({'data': data, 'totalCount': total_count})


@require_GET
def get_municipalities(request):
    province_id = request.GET.get('province_id')
    if province_id:
        try:
            province = Province.objects.get(id=province_id)
            municipalities = province.municipalities.all().order_by('name')
            options = ''.join([
                f'<option value="{m.id}">{escape(m.name)}</option>' for m in municipalities
            ])
            return HttpResponse(f'<option value="">---</option>{options}')
        except Province.DoesNotExist:
            pass
    return HttpResponse('<option value="">---</option>')


def _serialize_agent(agent, request):
    if agent is None:
        return None

    profile = getattr(agent, 'profile', None)

    return {
        'name': agent.get_full_name() or agent.username,
        'email': agent.email or '',
        'phone': profile.phone if profile else '',
        'avatar_url': (
            request.build_absolute_uri(profile.avatar.url)
            if profile and profile.avatar else None
        ),
        'agency_name': profile.agency_name if profile else '',
        'bio': profile.bio if profile else '',
        'user_type_display': profile.get_user_type_display() if profile else '',
    }


def _serialize_property_detail(obj, request):
    # Misma convención que la vista HTML (property_detail): la portada va
    # siempre primero en la lista, independientemente de su 'order', para
    # que el quick view de index.html no dependa de que el JS cliente
    # vuelva a buscarla por is_cover (que hoy hace como salvaguarda, pero
    # así ambos caminos quedan alineados en el origen).
    property_images = list(obj.images.all())
    cover = obj.cover_image
    if cover and property_images and property_images[0] != cover:
        property_images.remove(cover)
        property_images.insert(0, cover)

    images = [
        {
            'url': request.build_absolute_uri(img.image.url),
            'is_cover': img.is_cover,
        }
        for img in property_images
    ]
    # Si el inmueble todavía no tiene ninguna foto real, se deja la lista
    # vacía en vez de rellenarla con una imagen de stock de picsum.photos:
    # esa imagen no la subió nadie y el frontend la mostraba como si
    # fuera una foto real del inmueble (ver renderQuickViewGallery en
    # index.html, que ahora sabe pintar el estado "sin fotos").

    # Determinar precios para el detail
    sale_price = float(obj.sale_price) if obj.sale_price else None
    rent_price = float(obj.rent_price) if obj.rent_price else None
    seasonal_rent_price = float(obj.seasonal_rent_price) if obj.seasonal_rent_price else None
    deposit_amount = float(obj.deposit_amount) if obj.deposit_amount else None

    return {
        'id': obj.pk,
        'title': obj.safe_translation_getter('title', any_language=True) or '',
        'description': obj.safe_translation_getter('description', any_language=True) or '',
        'images': images,
        'offer_type': obj.offer_type,
        'offer_type_display': obj.get_offer_type_display(),
        'sale_price': sale_price,
        'rent_price': rent_price,
        'seasonal_rent_price': seasonal_rent_price,
        'deposit_amount': deposit_amount,
        'display_price': float(obj.display_price) if obj.display_price else None,
        'display_price_label': str(obj.display_price_label),
        'address': obj.address or '',
        'province': obj.province.name if obj.province else '',
        'municipality': obj.municipality.name if obj.municipality else '',
        'municipality_latitude': float(obj.municipality.latitude) if obj.municipality and obj.municipality.latitude else None,
        'municipality_longitude': float(obj.municipality.longitude) if obj.municipality and obj.municipality.longitude else None,
        'property_type': obj.get_property_type_display(),
        'rooms': obj.rooms,
        'bathrooms': obj.bathrooms,
        'surface': obj.surface,
        'has_elevator': obj.has_elevator,
        'has_heating': obj.has_heating,
        'has_air_conditioning': obj.has_air_conditioning,
        'status': obj.get_status_display(),
        'views_count': obj.views_count,
        'detail_url': reverse('properties:detail', args=[obj.pk, obj.slug]),
        'agent': _serialize_agent(obj.agent, request),
    }


@require_GET
def property_detail_json(request, pk):
    obj = get_object_or_404(
        Property.objects.select_related(
            'province', 'municipality', 'agent', 'agent__profile'
        ).prefetch_related('images'),
        pk=pk,
        is_active=True,
    )
    return JsonResponse(_serialize_property_detail(obj, request))