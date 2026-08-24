from django.apps import AppConfig


class VisorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.visor'
    label = 'visor'
    verbose_name = 'Visor de Logs'
