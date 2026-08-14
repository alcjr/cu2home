from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F
from django.views.decorators.http import require_GET

from .forms import PropertyFilterForm
from .models import Property, Province, Municipality
from .constants import PROPERTY_TYPES


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

    sort_param = request.GET.get('sort', '-created_at')
    allowed_sort = {
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'price': 'price',
        '-price': '-price',
        'surface': 'surface',
        '-surface': '-surface',
    }
    sort = allowed_sort.get(sort_param, '-created_at')
    properties = properties.order_by(sort)

    paginator = Paginator(properties, settings.SEARCH_RESULTS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'properties': page_obj,
        'form': form,
        'current_sort': sort_param if sort_param in allowed_sort else '-created_at',
    }

    if request.htmx:
        return render(request, 'properties/partials/list_results.html', context)

    return render(request, 'properties/list.html', context)


def property_detail(request, pk, slug):
    obj = get_object_or_404(Property, pk=pk, is_active=True)
    Property.objects.filter(pk=obj.pk).update(views_count=F('views_count') + 1)
    obj.refresh_from_db(fields=['views_count'])
    return render(request, 'properties/detail.html', {'property': obj})


@require_GET
def get_municipalities(request):
    """HTMX endpoint: devuelve los municipios de una provincia seleccionada."""
    province_id = request.GET.get('province_id')
    if province_id:
        try:
            province = Province.objects.get(id=province_id)
            municipalities = province.municipalities.all().order_by('name')
            options = ''.join([
                f'<option value="{m.id}">{m.name}</option>' for m in municipalities
            ])
            return HttpResponse(f'<option value="">---</option>{options}')
        except Province.DoesNotExist:
            pass
    return HttpResponse('<option value="">---</option>')