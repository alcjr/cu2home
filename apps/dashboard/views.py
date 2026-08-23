import json
import logging
from datetime import datetime
from collections import defaultdict

from django.shortcuts import render
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt

from apps.properties.models import Property, Province, Municipality, PropertyOfferType, PropertyStatus

logger = logging.getLogger(__name__)
User = get_user_model()


@staff_member_required
def dashboard(request):
    """Dashboard principal con todos los KPI y gráficos."""
    try:
        years = Property.objects.dates('created_at', 'year', order='DESC')
        
        context = {
            'provinces': Province.objects.all().order_by('name'),
            'municipalities': Municipality.objects.select_related('province').order_by('name'),
            'years': years,
        }
        return render(request, 'dashboard/dashboard.html', context)
    except Exception as e:
        logger.error(f"Error en dashboard: {e}", exc_info=True)
        return render(request, 'dashboard/dashboard.html', {
            'provinces': Province.objects.all().order_by('name'),
            'municipalities': Municipality.objects.select_related('province').order_by('name'),
            'years': [],
            'error': str(e),
        })


def safe_int(value, default=None):
    """Convierte un valor a entero de forma segura."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@staff_member_required
def dashboard_data(request):
    """API que devuelve todos los datos del dashboard en JSON."""
    try:
        # Parámetros de filtro
        province_id = safe_int(request.GET.get('province_id'))
        municipality_id = safe_int(request.GET.get('municipality_id'))
        year = safe_int(request.GET.get('year'))
        
        # Base queryset
        properties = Property.objects.all()
        
        # Aplicar filtros
        if province_id:
            properties = properties.filter(province_id=province_id)
        
        if municipality_id:
            properties = properties.filter(municipality_id=municipality_id)
        
        if year:
            properties = properties.filter(created_at__year=year)
        
        # ===== KPI =====
        total_properties = properties.count()
        
        # Inmuebles por estado
        active_properties = properties.filter(is_active=True).count()
        available_properties = properties.filter(status=PropertyStatus.AVAILABLE).count()
        reserved_properties = properties.filter(status=PropertyStatus.RESERVED).count()
        sold_properties = properties.filter(status=PropertyStatus.SOLD).count()
        
        # Inmuebles por tipo de oferta
        sale_properties = properties.filter(
            Q(offer_type=PropertyOfferType.SALE) | Q(offer_type=PropertyOfferType.SALE_OR_RENT)
        ).count()
        rent_properties = properties.filter(
            Q(offer_type=PropertyOfferType.RENT) | Q(offer_type=PropertyOfferType.SALE_OR_RENT)
        ).count()
        swap_properties = properties.filter(offer_type=PropertyOfferType.SWAP).count()
        sale_or_rent_properties = properties.filter(offer_type=PropertyOfferType.SALE_OR_RENT).count()
        
        # Porcentajes
        def pct(value):
            return round((value / total_properties * 100) if total_properties > 0 else 0, 1)
        
        kpi = {
            'total_properties': total_properties,
            'active_properties': active_properties,
            'active_percent': pct(active_properties),
            'available_properties': available_properties,
            'available_percent': pct(available_properties),
            'reserved_properties': reserved_properties,
            'reserved_percent': pct(reserved_properties),
            'sold_properties': sold_properties,
            'sold_percent': pct(sold_properties),
            'sale_properties': sale_properties,
            'sale_percent': pct(sale_properties),
            'rent_properties': rent_properties,
            'rent_percent': pct(rent_properties),
            'swap_properties': swap_properties,
            'swap_percent': pct(swap_properties),
            'sale_or_rent_properties': sale_or_rent_properties,
            'sale_or_rent_percent': pct(sale_or_rent_properties),
        }
        
        # ===== GRÁFICOS: Ventas/Alquiler/Permutas por mes =====
        def get_monthly_data(offer_type_filter=None, status_filter=None):
            qs = properties
            if offer_type_filter:
                qs = qs.filter(offer_type=offer_type_filter)
            if status_filter:
                qs = qs.filter(status=status_filter)
            
            # Obtener el año a usar
            use_year = year
            if not use_year:
                # Tomar el año más reciente con datos
                latest = qs.dates('created_at', 'year', order='DESC').first()
                if latest:
                    use_year = latest.year
            
            # Agrupar por mes
            monthly = qs.annotate(
                month=ExtractMonth('created_at'),
                year=ExtractYear('created_at')
            ).values('year', 'month').annotate(
                count=Count('id')
            ).order_by('year', 'month')
            
            if use_year:
                monthly = monthly.filter(year=use_year)
            
            # Rellenar meses faltantes
            months_data = {i: 0 for i in range(1, 13)}
            for item in monthly:
                months_data[item['month']] = item['count']
            
            return list(months_data.values())
        
        monthly_sales = get_monthly_data(
            offer_type_filter=PropertyOfferType.SALE,
            status_filter=PropertyStatus.SOLD
        )
        monthly_rents = get_monthly_data(
            offer_type_filter=PropertyOfferType.RENT,
            status_filter=PropertyStatus.SOLD
        )
        monthly_swaps = get_monthly_data(
            offer_type_filter=PropertyOfferType.SWAP,
            status_filter=PropertyStatus.SOLD
        )
        
        # ===== GRÁFICOS: Por municipio =====
        def get_municipality_data(offer_type_filter=None, status_filter=None):
            qs = properties
            if offer_type_filter:
                qs = qs.filter(offer_type=offer_type_filter)
            if status_filter:
                qs = qs.filter(status=status_filter)
            
            # Determinar qué provincia usar
            use_province_id = province_id
            if not use_province_id:
                top_province = qs.values('province').annotate(
                    count=Count('id')
                ).order_by('-count').first()
                if top_province and top_province['province']:
                    use_province_id = top_province['province']
            
            if use_province_id:
                qs = qs.filter(province_id=use_province_id)
            
            # Agrupar por municipio
            data = qs.values(
                'municipality_id', 'municipality__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            return {
                'names': [item['municipality__name'] or 'Sin municipio' for item in data],
                'values': [item['count'] for item in data],
            }
        
        municipality_sales = get_municipality_data(
            offer_type_filter=PropertyOfferType.SALE,
            status_filter=PropertyStatus.SOLD
        )
        municipality_rents = get_municipality_data(
            offer_type_filter=PropertyOfferType.RENT,
            status_filter=PropertyStatus.SOLD
        )
        municipality_swaps = get_municipality_data(
            offer_type_filter=PropertyOfferType.SWAP,
            status_filter=PropertyStatus.SOLD
        )
        
        # ===== PRECIO POR m² =====
        def get_price_per_sqm(offer_type_filter=None, status_filter=None):
            qs = properties.filter(
                surface__gt=0,
                sale_price__isnull=False
            )
            if offer_type_filter:
                qs = qs.filter(offer_type=offer_type_filter)
            if status_filter:
                qs = qs.filter(status=status_filter)
            
            # Determinar qué provincia usar
            use_province_id = province_id
            if not use_province_id:
                top_province = qs.values('province').annotate(
                    count=Count('id')
                ).order_by('-count').first()
                if top_province and top_province['province']:
                    use_province_id = top_province['province']
            
            if use_province_id:
                qs = qs.filter(province_id=use_province_id)
            
            if year:
                qs = qs.filter(created_at__year=year)
            
            # Agrupar por municipio y calcular precio/m² promedio
            data = qs.values(
                'municipality_id', 'municipality__name'
            ).annotate(
                avg_price_per_sqm=Avg('sale_price') / Avg('surface'),
                count=Count('id')
            ).filter(count__gt=1).order_by('-avg_price_per_sqm')
            
            return {
                'names': [item['municipality__name'] or 'Sin municipio' for item in data],
                'values': [round(float(item['avg_price_per_sqm']), 2) for item in data if item['avg_price_per_sqm'] is not None],
            }
        
        sale_price_per_sqm = get_price_per_sqm(
            offer_type_filter=PropertyOfferType.SALE,
            status_filter=PropertyStatus.SOLD
        )
        
        rent_price_per_sqm = get_price_per_sqm(
            offer_type_filter=PropertyOfferType.RENT,
            status_filter=PropertyStatus.SOLD
        )
        
        # ===== GRÁFICOS ADICIONALES =====
        
        # Distribución por tipo de propiedad
        property_type_distribution = list(properties.values(
            'property_type'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
        
        # Distribución por estado
        status_distribution = list(properties.values(
            'status'
        ).annotate(
            count=Count('id')
        ).order_by('-count'))
        
        # Precio promedio por tipo de propiedad
        avg_price_by_type = list(properties.filter(
            sale_price__isnull=False,
            status=PropertyStatus.SOLD
        ).values(
            'property_type'
        ).annotate(
            avg_price=Avg('sale_price')
        ).order_by('-avg_price'))
        
        # Top 5 provincias con más propiedades
        top_provinces = list(properties.values(
            'province__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5])
        
        response_data = {
            'kpi': kpi,
            'charts': {
                'monthly_sales': monthly_sales or [0] * 12,
                'monthly_rents': monthly_rents or [0] * 12,
                'monthly_swaps': monthly_swaps or [0] * 12,
                'municipality_sales': municipality_sales or {'names': [], 'values': []},
                'municipality_rents': municipality_rents or {'names': [], 'values': []},
                'municipality_swaps': municipality_swaps or {'names': [], 'values': []},
                'sale_price_per_sqm': sale_price_per_sqm or {'names': [], 'values': []},
                'rent_price_per_sqm': rent_price_per_sqm or {'names': [], 'values': []},
                'property_type_distribution': property_type_distribution,
                'status_distribution': status_distribution,
                'avg_price_by_type': avg_price_by_type,
                'top_provinces': top_provinces,
            },
            'filters': {
                'selected_province': province_id,
                'selected_municipality': municipality_id,
                'selected_year': year,
            }
        }
        
        return JsonResponse(response_data, encoder=DjangoJSONEncoder)
        
    except Exception as e:
        logger.error(f"Error en dashboard_data: {e}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'message': 'Error al cargar los datos del dashboard'
        }, status=500)


@staff_member_required
def test_json(request):
    """Vista de prueba para verificar que el JSON funciona."""
    return JsonResponse({
        'status': 'ok',
        'message': 'Dashboard funciona correctamente',
        'timestamp': datetime.now().isoformat()
    })