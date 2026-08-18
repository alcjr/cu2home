from django.utils.translation import gettext_lazy as _

PROPERTY_TYPES = [
    ('apartment', _('Apartment')),
    ('house', _('House')),
    ('villa', _('Villa')),
    ('commercial', _('Commercial')),
    ('land', _('Land')),
    ('other', _('Other')),
]

OFFER_TYPES = [
    ('sale', _('Sale')),
    ('rent', _('Rent')),
    ('swap', _('Swap')),
    ('sale_or_rent', _('Sale or Rent')),
]

DEFAULT_FAVORITE_LIST_NAME = _('My favorites')