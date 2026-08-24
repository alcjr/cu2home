from django.db import models
from django.utils.translation import gettext_lazy as _


class LogFilterPreset(models.Model):
    """Preset de filtros guardados para el visor de logs."""
    name = models.CharField(_('nombre'), max_length=100)
    level = models.CharField(
        _('nivel'),
        max_length=20,
        blank=True,
        choices=[
            ('', _('Todos')),
            ('DEBUG', 'DEBUG'),
            ('INFO', 'INFO'),
            ('WARNING', 'WARNING'),
            ('ERROR', 'ERROR'),
            ('CRITICAL', 'CRITICAL'),
        ]
    )
    search = models.CharField(_('búsqueda'), max_length=200, blank=True)
    lines_per_page = models.PositiveIntegerField(_('líneas por página'), default=100)
    created_at = models.DateTimeField(_('creado'), auto_now_add=True)

    class Meta:
        verbose_name = _('preset de filtro')
        verbose_name_plural = _('presets de filtros')
        ordering = ['-created_at']

    def __str__(self):
        return self.name
