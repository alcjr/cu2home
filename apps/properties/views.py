from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .forms import PropertyFilterForm
from .models import Property

# Whitelist explícita: nunca pasar request.GET['sort'] directo a order_by().
# Evita ordenar por campos de relación (agent__password) o provocar
# FieldError con nombres arbitrarios.
ALLOWED_SORT_FIELDS = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'price': 'price',
    '-price': '-price',
    'surface': 'surface',
    '-surface': '-surface',
}
DEFAULT_SORT = '-created_at'


def property_list(request):
    properties = Property.objects.filter(is_active=True)
    form = PropertyFilterForm(request.GET or None)

    if form.is_valid():
        data = form.cleaned_data
        if data.get('city'):
            properties = properties.filter(city__icontains=data['city'])
        if data.get('min_price') is not None:
            properties = properties.filter(price__gte=data['min_price'])
        if data.get('max_price') is not None:
            properties = properties.filter(price__lte=data['max_price'])
        if data.get('min_surface') is not None:
            properties = properties.filter(surface__gte=data['min_surface'])
        if data.get('max_surface') is not None:
            properties = properties.filter(surface__lte=data['max_surface'])
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

    sort_param = request.GET.get('sort', DEFAULT_SORT)
    sort = ALLOWED_SORT_FIELDS.get(sort_param, DEFAULT_SORT)
    properties = properties.order_by(sort)

    paginator = Paginator(properties, settings.SEARCH_RESULTS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'properties': page_obj,
        'form': form,
        'current_sort': sort_param if sort_param in ALLOWED_SORT_FIELDS else DEFAULT_SORT,
    }

    if request.htmx:
        return render(request, 'properties/partials/list_results.html', context)

    return render(request, 'properties/list.html', context)


def property_detail(request, pk, slug):
    # `slug` es decorativo (SEO); la búsqueda real va por pk. No se fuerza
    # redirect canónico todavía -- pendiente si se quiere ese comportamiento.
    obj = get_object_or_404(Property, pk=pk, is_active=True)

    # Incremento atómico: evita perder vistas por condiciones de carrera
    # bajo tráfico concurrente (el patrón anterior leía y escribía en dos
    # pasos no atómicos).
    Property.objects.filter(pk=obj.pk).update(views_count=F('views_count') + 1)
    obj.refresh_from_db(fields=['views_count'])

    return render(request, 'properties/detail.html', {'property': obj})
