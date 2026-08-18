from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from .models import Property, PropertyImage, Province, Municipality, PropertyOfferType
from django.conf import settings

# MAX_IMAGES_PER_PROPERTY se importa desde settings
MAX_IMAGES_PER_PROPERTY = settings.MAX_IMAGES_PER_PROPERTY


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('preview', 'image', 'is_cover', 'order')
    readonly_fields = ('preview',)

    def preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;" />',
                obj.image.url,
            )
        return '—'
    preview.short_description = _('Preview')

    def get_max_num(self, request, obj=None, **kwargs):
        if obj is None:
            return MAX_IMAGES_PER_PROPERTY
        remaining = MAX_IMAGES_PER_PROPERTY - obj.images.count()
        return max(remaining, 0)

    def has_add_permission(self, request, obj=None):
        if obj is not None and obj.images.count() >= MAX_IMAGES_PER_PROPERTY:
            return False
        return super().has_add_permission(request, obj)


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'province', 'slug')
    list_filter = ('province',)
    search_fields = ('name', 'province__name')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 
        'property_type', 
        'offer_type',
        'city', 
        'municipality', 
        'sale_price',
        'rent_price',
        'image_count', 
        'is_active', 
        'created_at'
    )
    list_filter = (
        'property_type', 
        'offer_type',
        'is_active', 
        'city', 
        'province', 
        'municipality', 
        'has_elevator', 
        'has_heating', 
        'has_air_conditioning'
    )
    search_fields = ('translations__title', 'city', 'province__name', 'municipality__name', 'slug')
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    inlines = [PropertyImageInline]
    autocomplete_fields = ('province', 'municipality', 'agent')
    
    fieldsets = (
        (None, {
            'fields': ('translations', 'property_type', 'offer_type')
        }),
        (_('Pricing'), {
            'fields': ('sale_price', 'rent_price', 'seasonal_rent_price', 'deposit_amount'),
            'classes': ('wide',),
        }),
        (_('Location'), {
            'fields': ('city', 'province', 'municipality', 'address', 'location')
        }),
        (_('Details'), {
            'fields': ('surface', 'rooms', 'bathrooms', 'has_elevator', 'has_heating', 'has_air_conditioning')
        }),
        (_('Metadata'), {
            'fields': ('slug', 'is_active', 'views_count', 'agent', 'status', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('province', 'municipality').prefetch_related('images').annotate(
            _image_count=Count('images')
        )

    def image_count(self, obj):
        return getattr(obj, '_image_count', obj.images.count())
    image_count.short_description = _('Images')
    image_count.admin_order_field = '_image_count'


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_cover', 'order', 'created_at')
    list_filter = ('is_cover',)
    autocomplete_fields = ('property',)