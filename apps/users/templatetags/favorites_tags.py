# apps/users/templatetags/favorites_tags.py
from django import template
from apps.users.models import Favorite

register = template.Library()

@register.simple_tag
def is_favorited(user, property_obj):
    if not user.is_authenticated:
        return False
    return Favorite.objects.filter(user=user, property=property_obj).exists()