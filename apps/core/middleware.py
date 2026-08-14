from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

class ActiveLanguageMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Lógica para forzar idioma, por ejemplo, desde sesión o cookie
        # Por defecto, usa el de la sesión o el predeterminado
        pass