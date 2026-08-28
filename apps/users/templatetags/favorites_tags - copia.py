from django import template

from apps.users.models import Favorite

register = template.Library()


@register.simple_tag
def is_favorited(user, property):
    """
    {% is_favorited user property as is_fav %}

    Devuelve True/False según si `property` está en los favoritos de
    `user`. Vive aquí (apps.users) en vez de en apps.properties porque
    el modelo Favorite también vive aquí -- así detail.html (de
    apps.properties) puede consultarlo sin que esa app tenga que
    importar nada de apps.users en su vista.

    Usuarios anónimos siempre devuelven False sin tocar la base de
    datos -- el botón de favoritos ya está oculto para ellos en la
    plantilla, pero esto blinda el tag por si se usa en otro sitio.
    """
    if not user.is_authenticated:
        return False
    return Favorite.objects.filter(user=user, property=property).exists()
