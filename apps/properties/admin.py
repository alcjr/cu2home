from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import MAX_IMAGES_PER_PROPERTY, Property, PropertyImage


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


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'property_type', 'city', 'price', 'image_count', 'is_active', 'created_at')
    list_filter = ('property_type', 'is_active', 'city', 'has_elevator', 'has_heating', 'has_air_conditioning')
    search_fields = ('translations__title', 'city', 'province', 'slug')
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    inlines = [PropertyImageInline]

    def image_count(self, obj):
        return obj.image_count
    image_count.short_description = _('Images')


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'is_cover', 'order', 'created_at')
    list_filter = ('is_cover',)
    autocomplete_fields = ('property',)