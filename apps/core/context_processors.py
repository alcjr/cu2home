from django.conf import settings

def site_settings(request):
    """
    Context processor para añadir variables globales a todos los templates.
    """
    return {
        'site_name': getattr(settings, 'SITE_NAME', 'cu2home'),
        'site_description': getattr(settings, 'SITE_DESCRIPTION', 'Portal inmobiliario en Cuba'),
        'LANGUAGES': settings.LANGUAGES,
        'LANGUAGE_CODE': getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE),
    }
