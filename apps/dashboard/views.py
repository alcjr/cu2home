import json
import logging
import os
from datetime import datetime
from collections import defaultdict

from django.shortcuts import render
from django.db import connection
from django.db.models import Count, Sum, Avg, Q, F, FloatField
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings

from apps.properties.models import Property, Province, Municipality, PropertyOfferType, PropertyStatus

logger = logging.getLogger(__name__)
User = get_user_model()


# =============================================================================
# UTILIDADES
# =============================================================================

def safe_int(value, default=None):
    """Convierte un valor a entero de forma segura."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_div(a, b, default=0):
    """División segura que evita ZeroDivisionError."""
    try:
        return a / b
    except (ZeroDivisionError, TypeError):
        return default


def pct(value, total):
    """Calcula porcentaje redondeado a 1 decimal."""
    return round((value / total * 100) if total > 0 else 0, 1)


# =============================================================================
# ALMACENAMIENTO (tamaño de BD e imágenes)
# =============================================================================

STORAGE_CACHE_KEY = 'dashboard_storage_usage'
STORAGE_CACHE_TIMEOUT = 60 * 30  # 30 minutos: evita recalcular en cada filtro


def get_database_size_mb():
    """
    Tamaño total de la base de datos PostgreSQL (cu2home_db) en MB,
    usando la función nativa pg_database_size().
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            size_bytes = cursor.fetchone()[0]
        return round(size_bytes / (1024 * 1024), 2)
    except Exception as e:
        logger.error(f"Error obteniendo tamaño de la base de datos: {e}", exc_info=True)
        return None


def get_directory_size_mb(path):
    """Suma recursiva del tamaño (en MB) de todos los archivos bajo `path`."""
    total_bytes = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.isfile(filepath):
                    total_bytes += os.path.getsize(filepath)
    except FileNotFoundError:
        return 0.0
    except Exception as e:
        logger.error(f"Error calculando tamaño de '{path}': {e}", exc_info=True)
        return None
    return round(total_bytes / (1024 * 1024), 2)


def get_images_size_mb():
    """
    Tamaño en MB de las imágenes de inmuebles subidas por los usuarios.
    Usa MEDIA_ROOT como raíz de archivos servidos por Django.
    Ajustar el subdirectorio si las imágenes de propiedades se guardan en
    una carpeta específica (ej. MEDIA_ROOT / 'properties').
    """
    return get_directory_size_mb(settings.MEDIA_ROOT)


def get_storage_usage():
    """
    Devuelve {'database_mb': ..., 'images_mb': ...}, cacheado porque
    recorrer el disco y consultar pg_database_size en cada petición
    de filtro sería costoso e innecesario (el dato no depende de los filtros).
    """
    cached = cache.get(STORAGE_CACHE_KEY)
    if cached is not None:
        return cached

    data = {
        'database_mb': get_database_size_mb(),
        'images_mb': get_images_size_mb(),
    }
    cache.set(STORAGE_CACHE_KEY, data, STORAGE_CACHE_TIMEOUT)
    return data


# =============================================================================
# SERVICIOS DE DATOS
# =============================================================================

class DashboardDataService:
    """Servicio que encapsula toda la lógica de consulta de datos del dashboard."""

    MONTHS = list(range(1, 13))

    def __init__(self, request):
        self.province_id = safe_int(request.GET.get('province_id'))
        self.municipality_id = safe_int(request.GET.get('municipality_id'))
        self.year = safe_int(request.GET.get('year'))
        self._base_qs = self._build_base_queryset()
        self._resolved_year = self._resolve_reference_year()

    def _build_base_queryset(self):
        """Construye el queryset base aplicando filtros de usuario."""
        qs = Property.objects.all()
        if self.province_id:
            qs = qs.filter(province_id=self.province_id)
        if self.municipality_id:
            qs = qs.filter(municipality_id=self.municipality_id)
        if self.year:
            qs = qs.filter(created_at__year=self.year)
        return qs

    def _resolve_reference_year(self):
        """
        Determina un año de referencia único para todos los gráficos mensuales.
        Si el usuario filtró por año, se usa ese. Si no, se toma el año más
        reciente con datos en el queryset base.
        """
        if self.year:
            return self.year
        latest = self._base_qs.dates('created_at', 'year', order='DESC').first()
        return latest.year if latest else datetime.now().year

    def _apply_province_fallback(self, qs):
        """
        Si no hay filtro de provincia, restringe el queryset a la provincia
        con más registros para mantener coherencia visual en gráficos por municipio.
        """
        if self.province_id:
            return qs.filter(province_id=self.province_id)
        top = qs.values('province').annotate(count=Count('id')).order_by('-count').first()
        if top and top['province']:
            return qs.filter(province_id=top['province'])
        return qs

    # -------------------------------------------------------------------------
    # KPI
    # -------------------------------------------------------------------------

    def get_kpi(self):
        total = self._base_qs.count()

        active = self._base_qs.filter(is_active=True).count()
        available = self._base_qs.filter(status=PropertyStatus.AVAILABLE).count()
        reserved = self._base_qs.filter(status=PropertyStatus.RESERVED).count()
        sold = self._base_qs.filter(status=PropertyStatus.SOLD).count()

        # Ofertas: MUTUAMENTE EXCLUSIVAS para que los porcentajes suman ≤ 100%
        sale_only = self._base_qs.filter(offer_type=PropertyOfferType.SALE).count()
        rent_only = self._base_qs.filter(offer_type=PropertyOfferType.RENT).count()
        swap_only = self._base_qs.filter(offer_type=PropertyOfferType.SWAP).count()
        sale_or_rent = self._base_qs.filter(offer_type=PropertyOfferType.SALE_OR_RENT).count()

        return {
            'total_properties': total,
            'active_properties': active,
            'active_percent': pct(active, total),
            'available_properties': available,
            'available_percent': pct(available, total),
            'reserved_properties': reserved,
            'reserved_percent': pct(reserved, total),
            'sold_properties': sold,
            'sold_percent': pct(sold, total),
            'sale_properties': sale_only,
            'sale_percent': pct(sale_only, total),
            'rent_properties': rent_only,
            'rent_percent': pct(rent_only, total),
            'swap_properties': swap_only,
            'swap_percent': pct(swap_only, total),
            'sale_or_rent_properties': sale_or_rent,
            'sale_or_rent_percent': pct(sale_or_rent, total),
        }

    # -------------------------------------------------------------------------
    # SERIES TEMPORALES (mensuales)
    # -------------------------------------------------------------------------

    def get_monthly_data(self, offer_type_filter=None):
        """
        Devuelve array de 12 posiciones con conteos por mes para el año de referencia.
        NO aplica filtro de status para no forzar SOLD en alquileres/permutas.
        """
        qs = self._base_qs
        if offer_type_filter:
            qs = qs.filter(offer_type=offer_type_filter)

        monthly = (
            qs.annotate(month=ExtractMonth('created_at'), year=ExtractYear('created_at'))
              .filter(year=self._resolved_year)
              .values('month')
              .annotate(count=Count('id'))
              .order_by('month')
        )

        data = {i: 0 for i in self.MONTHS}
        for item in monthly:
            data[item['month']] = item['count']
        return [data[i] for i in self.MONTHS]

    # -------------------------------------------------------------------------
    # GEOGRÁFICOS (por municipio)
    # -------------------------------------------------------------------------

    def get_municipality_data(self, offer_type_filter=None, limit=15):
        """
        Top N municipios para un tipo de oferta. Usa la misma provincia fallback
        que el resto de gráficos para coherencia.
        """
        qs = self._base_qs
        if offer_type_filter:
            qs = qs.filter(offer_type=offer_type_filter)

        qs = self._apply_province_fallback(qs)

        data = (
            qs.values('municipality_id', 'municipality__name')
              .annotate(count=Count('id'))
              .order_by('-count')[:limit]
        )

        return {
            'names': [item['municipality__name'] or _('Sin municipio') for item in data],
            'values': [item['count'] for item in data],
        }

    # -------------------------------------------------------------------------
    # PRECIO POR M²
    # -------------------------------------------------------------------------

    def get_price_per_sqm(self, offer_type_filter=None, limit=15):
        """
        Precio medio por m² calculado como AVG(precio / superficie).
        Filtra registros con superficie > 0 y precio no nulo.
        """
        qs = self._base_qs.filter(surface__gt=0, sale_price__isnull=False)
        if offer_type_filter:
            qs = qs.filter(offer_type=offer_type_filter)

        qs = self._apply_province_fallback(qs)

        data = (
            qs.values('municipality_id', 'municipality__name')
              .annotate(
                  avg_price_per_sqm=Avg(
                      F('sale_price') / F('surface'),
                      output_field=FloatField()
                  ),
                  count=Count('id')
              )
              .filter(count__gt=1)
              .order_by('-avg_price_per_sqm')[:limit]
        )

        return {
            'names': [item['municipality__name'] or _('Sin municipio') for item in data],
            'values': [
                round(float(item['avg_price_per_sqm']), 2)
                for item in data
                if item['avg_price_per_sqm'] is not None
            ],
        }

    # -------------------------------------------------------------------------
    # DISTRIBUCIONES Y TOP
    # -------------------------------------------------------------------------

    def get_property_type_distribution(self):
        return list(
            self._base_qs.values('property_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    def get_status_distribution(self):
        return list(
            self._base_qs.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    def get_top_provinces(self, limit=5):
        return list(
            self._base_qs.values('province__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )

    # -------------------------------------------------------------------------
    # ENSAMBLAJE
    # -------------------------------------------------------------------------

    def build_response(self):
        return {
            'kpi': self.get_kpi(),
            'charts': {
                'monthly_sales': self.get_monthly_data(offer_type_filter=PropertyOfferType.SALE),
                'monthly_rents': self.get_monthly_data(offer_type_filter=PropertyOfferType.RENT),
                'monthly_swaps': self.get_monthly_data(offer_type_filter=PropertyOfferType.SWAP),
                'municipality_sales': self.get_municipality_data(offer_type_filter=PropertyOfferType.SALE),
                'municipality_rents': self.get_municipality_data(offer_type_filter=PropertyOfferType.RENT),
                'municipality_swaps': self.get_municipality_data(offer_type_filter=PropertyOfferType.SWAP),
                'sale_price_per_sqm': self.get_price_per_sqm(offer_type_filter=PropertyOfferType.SALE),
                'rent_price_per_sqm': self.get_price_per_sqm(offer_type_filter=PropertyOfferType.RENT),
                'property_type_distribution': self.get_property_type_distribution(),
                'status_distribution': self.get_status_distribution(),
                'top_provinces': self.get_top_provinces(),
            },
            'storage': get_storage_usage(),
            'meta': {
                'reference_year': self._resolved_year,
                'currency': getattr(settings, 'CURRENCY_SYMBOL', '€'),
            },
            'filters': {
                'selected_province': self.province_id,
                'selected_municipality': self.municipality_id,
                'selected_year': self.year,
            }
        }


# =============================================================================
# VISTAS
# =============================================================================

@staff_member_required
def dashboard(request):
    """Dashboard principal con todos los KPI y gráficos."""
    context = {
        'provinces': [],
        'municipalities': [],
        'years': [],
    }
    try:
        context['provinces'] = list(Province.objects.all().order_by('name').values('id', 'name'))
        context['municipalities'] = list(
            Municipality.objects.select_related('province')
            .order_by('name')
            .values('id', 'name', 'province_id')
        )
        context['years'] = list(
            Property.objects.dates('created_at', 'year', order='DESC')
        )
    except Exception as e:
        logger.error(f"Error cargando contexto del dashboard: {e}", exc_info=True)
        context['load_error'] = str(e)

    return render(request, 'dashboard/dashboard.html', context)


@staff_member_required
def dashboard_data(request):
    """API que devuelve todos los datos del dashboard en JSON."""
    try:
        service = DashboardDataService(request)
        return JsonResponse(service.build_response(), encoder=DjangoJSONEncoder)
    except Exception as e:
        logger.error(f"Error en dashboard_data: {e}", exc_info=True)
        return JsonResponse(
            {'error': str(e), 'message': _('Error al cargar los datos del dashboard')},
            status=500
        )


def test_json(request):
    """Vista de prueba para verificar que el JSON funciona. Solo disponible en DEBUG."""
    return JsonResponse({
        'status': 'ok',
        'message': 'Dashboard funciona correctamente',
        'timestamp': datetime.now().isoformat()
    })
