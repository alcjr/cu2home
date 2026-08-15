from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from parler.models import TranslatableModel, TranslatedFields

from .constants import PROPERTY_TYPES

MAX_IMAGES_PER_PROPERTY = settings.MAX_IMAGES_PER_PROPERTY


# ===== GEOGRAFÍA DE CUBA =====
class Province(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Province'))
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name=_('Slug'))

    class Meta:
        verbose_name = _('Province')
        verbose_name_plural = _('Provinces')
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Municipality(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='municipalities', verbose_name=_('Province'))
    name = models.CharField(max_length=100, verbose_name=_('Municipality'))
    slug = models.SlugField(max_length=100, blank=True, verbose_name=_('Slug'))

    class Meta:
        verbose_name = _('Municipality')
        verbose_name_plural = _('Municipalities')
        ordering = ['province__name', 'name']
        unique_together = ('province', 'name')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.province.name})"


# ===== PROPIEDADES =====
def property_image_upload_path(instance, filename):
    return f'properties/{instance.property_id}/images/{filename}'


class PropertyStatus(models.TextChoices):
    AVAILABLE = 'available', _('Available')
    RESERVED = 'reserved', _('Reserved')
    SOLD = 'sold', _('Sold')


class Property(TranslatableModel):
    translations = TranslatedFields(
        title=models.CharField(max_length=200, verbose_name=_('Title')),
        description=models.TextField(verbose_name=_('Description')),
    )
    property_type = models.CharField(
        max_length=50,
        choices=PROPERTY_TYPES,
        default='apartment',
        verbose_name=_('Property type'),
        db_index=True,
    )
    city = models.CharField(max_length=100, verbose_name=_('City'), db_index=True)
    province = models.ForeignKey(
        Province,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties',
        verbose_name=_('Province'),
        db_index=True,
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties',
        verbose_name=_('Municipality'),
        db_index=True,
    )
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name=_('Address'))
    location = gis_models.PointField(srid=4326, verbose_name=_('Location'), null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Price'), db_index=True)
    surface = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Surface (m²)'), db_index=True)
    rooms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Rooms'), db_index=True)
    bathrooms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Bathrooms'), db_index=True)
    has_elevator = models.BooleanField(default=False, verbose_name=_('Elevator'))
    has_heating = models.BooleanField(default=False, verbose_name=_('Heating'))
    has_air_conditioning = models.BooleanField(default=False, verbose_name=_('Air conditioning'))
    slug = models.SlugField(max_length=200, unique=True, verbose_name=_('Slug'), db_index=True)
    is_active = models.BooleanField(default=True, verbose_name=_('Active'), db_index=True)
    views_count = models.PositiveIntegerField(default=0, verbose_name=_('Views'))
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties',
        verbose_name=_('Agent'),
    )
    status = models.CharField(
        max_length=20,
        choices=PropertyStatus.choices,
        default=PropertyStatus.AVAILABLE,
        verbose_name=_('Status'),
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Property')
        verbose_name_plural = _('Properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['province', 'municipality']),
            models.Index(fields=['price', 'surface']),
        ]

    def __str__(self):
        try:
            return self.safe_translation_getter('title', any_language=True) or str(self.pk)
        except AttributeError:
            return str(self.pk)

    @property
    def image_count(self):
        return self.images.count()

    @classmethod
    def get_featured(cls, limit=6):
        """Retorna propiedades destacadas (las más recientes activas)"""
        return cls.objects.filter(is_active=True).select_related('province', 'municipality')[:limit]


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Property'),
    )
    image = models.ImageField(
        upload_to=property_image_upload_path,
        verbose_name=_('Image'),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    is_cover = models.BooleanField(default=False, verbose_name=_('Cover image'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Image')
        verbose_name_plural = _('Images')
        ordering = ['order']

    def __str__(self):
        return f'Image for {self.property}'


class SavedSearch(models.Model):
    class Frequency(models.TextChoices):
        IMMEDIATE = 'immediate', _('Immediate')
        DAILY = 'daily', _('Daily')
        WEEKLY = 'weekly', _('Weekly')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_searches',
        verbose_name=_('User'),
    )
    name = models.CharField(max_length=100, blank=True, verbose_name=_('Name'))
    query_params = models.JSONField(default=dict, verbose_name=_('Search parameters'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.DAILY,
        verbose_name=_('Frequency'),
    )
    last_sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Last sent'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Saved search')
        verbose_name_plural = _('Saved searches')

    def __str__(self):
        return f'{self.user} - {self.name or "Search"}'