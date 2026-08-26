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
    }
