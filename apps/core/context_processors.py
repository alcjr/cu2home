from django.conf import settings

def site_settings(request):
    """
    Context processor para añadir variables globales a todos los templates.
    """
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'cu2home'),
        'SITE_DESCRIPTION': getattr(settings, 'SITE_DESCRIPTION', 'Portal inmobiliario en Cuba'),
        'LANGUAGES': settings.LANGUAGES,
        'LANGUAGE_CODE': getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE),
    }