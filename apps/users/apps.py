from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'

    def ready(self):
        # Import dentro de ready(), no a nivel de módulo: en el momento en
        # que Django importa apps.py los modelos de otras apps (incluido
        # auth.User) todavía pueden no estar cargados del todo -- importar
        # signals.py (que importa UserProfile) aquí evita AppRegistryNotReady.
        from . import signals  # noqa: F401
