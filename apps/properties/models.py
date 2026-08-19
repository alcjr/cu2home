from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from parler.models import TranslatableModel, TranslatedFields

from .constants import PROPERTY_TYPES

# MAX_IMAGES_PER_PROPERTY se importa directamente desde settings
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
    
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True, 
        verbose_name=_('Latitude')
    )
    longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7, 
        null=True, 
        blank=True, 
        verbose_name=_('Longitude')
    )
    location = gis_models.PointField(
        srid=4326, 
        verbose_name=_('Location'), 
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = _('Municipality')
        verbose_name_plural = _('Municipalities')
        ordering = ['province__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['province', 'name'], name='unique_province_municipality_name'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        if self.latitude is not None and self.longitude is not None:
            self.location = Point(float(self.longitude), float(self.latitude), srid=4326)
        
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


class PropertyOfferType(models.TextChoices):
    SALE = 'sale', _('Sale')
    RENT = 'rent', _('Rent')
    SWAP = 'swap', _('Swap')
    SALE_OR_RENT = 'sale_or_rent', _('Sale or Rent')


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
    
    # === OFERTA ===
    offer_type = models.CharField(
        max_length=20,
        choices=PropertyOfferType.choices,
        default=PropertyOfferType.SALE,
        verbose_name=_('Offer type'),
        db_index=True,
    )
    
    # === PRECIOS ===
    sale_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name=_('Sale price'),
        db_index=True,
        help_text=_('Required if offering for sale')
    )
    
    rent_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name=_('Rent price (monthly)'),
        db_index=True,
        help_text=_('Required if offering for rent')
    )
    
    seasonal_rent_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name=_('Seasonal rent price (daily)'),
        help_text=_('Price per day for seasonal rentals')
    )
    
    deposit_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name=_('Deposit amount'),
        help_text=_('Security deposit for rentals')
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
            models.Index(fields=['sale_price', 'rent_price']),
        ]

    def __str__(self):
        try:
            return self.safe_translation_getter('title', any_language=True) or str(self.pk)
        except AttributeError:
            return str(self.pk)

    @property
    def image_count(self):
        return self.images.count()

    @property
    def cover_image(self):
        """
        Devuelve la PropertyImage marcada como portada (is_cover=True); si
        ninguna lo está, cae a la primera según Meta.ordering (`order`).
        None si el inmueble no tiene ninguna imagen.

        Fuente única de verdad para "qué imagen se muestra como portada":
        la usan tanto los templates (ficha de detalle) como los
        serializadores JSON (grid/quick-view) para no duplicar este
        criterio en varios sitios y evitar que diverjan.

        Si la relación 'images' ya fue precargada con prefetch_related,
        list(self.images.all()) reutiliza esa caché y no dispara consulta
        adicional.
        """
        images = list(self.images.all())
        if not images:
            return None
        return next((img for img in images if img.is_cover), images[0])

    @property
    def display_price(self):
        """Devuelve el precio principal según la oferta"""
        if self.offer_type == PropertyOfferType.SALE:
            return self.sale_price
        elif self.offer_type == PropertyOfferType.RENT:
            return self.rent_price
        elif self.offer_type == PropertyOfferType.SALE_OR_RENT:
            return self.sale_price or self.rent_price
        return self.sale_price or self.rent_price

    @property
    def display_price_label(self):
        """Etiqueta del precio mostrado"""
        if self.offer_type == PropertyOfferType.SALE:
            return _('Sale price')
        elif self.offer_type == PropertyOfferType.RENT:
            return _('Rent price (monthly)')
        elif self.offer_type == PropertyOfferType.SALE_OR_RENT:
            return _('Sale / Rent')
        return _('Price')

    @property
    def price_range_display(self):
        """Muestra el rango de precios si aplica"""
        if self.offer_type == PropertyOfferType.SALE_OR_RENT:
            parts = []
            if self.sale_price:
                parts.append(f"{_('Sale')}: {self.sale_price}")
            if self.rent_price:
                parts.append(f"{_('Rent')}: {self.rent_price}/mes")
            return " | ".join(parts)
        return str(self.display_price)

    def get_price_for_offer_type(self, offer_type):
        """Obtiene el precio según el tipo de oferta"""
        if offer_type == 'sale':
            return self.sale_price
        elif offer_type == 'rent':
            return self.rent_price
        return None

    def clean(self):
        """Validación personalizada del modelo"""
        from django.core.exceptions import ValidationError
        
        if self.offer_type in ['sale', 'sale_or_rent'] and not self.sale_price:
            raise ValidationError({
                'sale_price': _('Sale price is required for sale offers')
            })
        if self.offer_type in ['rent', 'sale_or_rent'] and not self.rent_price:
            raise ValidationError({
                'rent_price': _('Rent price is required for rent offers')
            })

    @classmethod
    def get_featured(cls, limit=6):
        """Retorna propiedades destacadas (las más recientes activas)"""
        return cls.objects.filter(is_active=True).select_related(
            'province', 'municipality'
        )[:limit]


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