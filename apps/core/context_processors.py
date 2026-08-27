from django.conf import settings
from django.utils import translation


def site_settings(request):
    """
    Context processor para añadir variables globales a todos los templates.
    """
    # --- Ruta "neutra" (sin prefijo de idioma) para el selector ES/EN ---
    # Django da prioridad al prefijo de idioma de la URL (/en/...) sobre la
    # cookie/sesión fijada por la vista `set_language`. Si el "next" del
    # formulario de cambio de idioma incluye ese prefijo, al volver a
    # español la URL sigue apuntando a /en/... y el idioma nunca cambia.
    # Por eso se limpia aquí el prefijo antes de exponerlo al template.
    full_path = request.get_full_path()
    lang_from_path = translation.get_language_from_path(request.path_info)
    if lang_from_path:
        prefix = f'/{lang_from_path}/'
        if full_path.startswith(prefix):
            full_path = '/' + full_path[len(prefix):]
    # ----------------------------------------------------------------

    return {
        'site_name': getattr(settings, 'SITE_NAME', 'cu2home'),
        'site_description': getattr(settings, 'SITE_DESCRIPTION', 'Portal inmobiliario en Cuba'),
        'LANGUAGES': settings.LANGUAGES,
        'LANGUAGE_CODE': getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE),
        'lang_switch_next': full_path or '/',
        # FIX (mapas mostrando "API KEY REQUIRED"): settings.py ya
        # calcula estos valores desde config.ini (con fallback a las
        # teselas estándar de OpenStreetMap, gratuitas y sin API key),
        # pero no llegaban a los templates porque este processor nunca
        # los incluía en el diccionario devuelto -- cualquier plantilla
        # que los usara (p.ej. el mapa de "Ubicación" o el quick view
        # del listado) tenía que codificar su propio proveedor de
        # teselas a mano, que es como se coló CartoDB (cuyo acceso
        # gratuito ya no existe) en index.html.
        'tile_layer_url': getattr(
            settings, 'TILE_LAYER_URL', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        ),
        'tile_layer_attribution': getattr(
            settings, 'TILE_LAYER_ATTRIBUTION', '&copy; OpenStreetMap contributors'
        ),
        'default_map_center_lat': getattr(settings, 'DEFAULT_MAP_CENTER_LAT', 23.0),
        'default_map_center_lng': getattr(settings, 'DEFAULT_MAP_CENTER_LNG', -82.0),
        'default_map_zoom': getattr(settings, 'DEFAULT_MAP_ZOOM', 7),
    }
