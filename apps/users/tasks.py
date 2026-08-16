import logging
from datetime import timedelta
from smtplib import SMTPException

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.properties.models import Property, SavedSearch

logger = logging.getLogger(__name__)

# Movido aquí desde el management command (antes vivía como constante de
# módulo en send_saved_search_alerts.py). Este archivo es ahora la única
# fuente de verdad de la lógica de envío; el management command es un
# wrapper fino que llama a dispatch_saved_search_alerts().
MIN_HOURS_BETWEEN_DAILY_ALERTS = 20
# Igual que MIN_HOURS_BETWEEN_DAILY_ALERTS pero para SavedSearch.Frequency.WEEKLY.
# Sin este throttle, como el beat dispara dispatch_saved_search_alerts cada
# hora (ver CELERY_BEAT_SCHEDULE), una alerta WEEKLY con resultados nuevos
# se reenviaría en cada tick horario en vez de una vez por semana.
MIN_HOURS_BETWEEN_WEEKLY_ALERTS = 24 * 7


@shared_task(
    bind=True,
    # Solo se reintenta ante fallos de SMTP (servidor caído, timeout,
    # rechazo temporal). Un SavedSearch.DoesNotExist o un error de
    # template es un bug, no algo transitorio -- no tiene sentido
    # reintentarlo, así que NO se incluye en autoretry_for.
    autoretry_for=(SMTPException,),
    retry_backoff=True,      # 1º reintento ~1s, luego exponencial
    retry_backoff_max=600,   # tope de 10 min entre reintentos
    retry_jitter=True,       # evita que varios workers reintenten a la vez
    max_retries=5,
)
def deliver_saved_search_alert(self, saved_search_id, match_ids):
    """
    Envía el email de UNA alerta ya calculada. `match_ids` se recibe como
    lista de pks (no un queryset) porque dispatch_saved_search_alerts()
    la calcula en el momento del dispatch y esta tarea puede ejecutarse
    minutos después (cola llena) o reintentarse -- pasar ids congela el
    conjunto de resultados y evita que un reintento incluya de más o de
    menos inmuebles por cambios que hayan ocurrido mientras tanto.
    """
    try:
        saved_search = SavedSearch.objects.select_related('user').get(pk=saved_search_id)
    except SavedSearch.DoesNotExist:
        logger.warning('SavedSearch %s ya no existe, se omite el envío.', saved_search_id)
        return

    matches = Property.objects.filter(pk__in=match_ids)
    if not matches.exists():
        # Los inmuebles pudieron desactivarse/borrarse entre el dispatch
        # y la ejecución real de la tarea.
        return

    subject = f'cu2home · {matches.count()} nuevo(s) inmueble(s) para "{saved_search}"'
    body = render_to_string('properties/emails/saved_search_alert.txt', {
        'saved_search': saved_search,
        'matches': matches,
    })

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # usa settings.DEFAULT_FROM_EMAIL
        recipient_list=[saved_search.user.email],
        fail_silently=False,
    )


@shared_task
def dispatch_saved_search_alerts():
    """
    Orquestador: recorre las SavedSearch activas y encola una tarea de
    envío individual por cada una que tenga resultados nuevos. Reemplaza
    el bucle síncrono que antes vivía directo en el management command --
    aquí solo se decide QUÉ enviar y se actualiza last_notified_at; el
    envío en sí (I/O de red hacia el SMTP) queda delegado a
    deliver_saved_search_alert, que puede fallar y reintentar de forma
    independiente sin bloquear ni repetir el resto del lote.

    Se dispara cada hora vía CELERY_BEAT_SCHEDULE (ver settings.py) y
    también puede lanzarse a mano con
    `manage.py send_saved_search_alerts`.
    """
    now = timezone.now()
    dispatched = 0
    skipped = 0

    searches = SavedSearch.objects.filter(is_active=True).select_related('user', 'user__profile')

    for saved_search in searches:
        if not saved_search.user.email:
            skipped += 1
            continue

        # Opt-out global vía UserProfile.receive_email_alerts (apps.users).
        # getattr con default True: usuarios creados ANTES de que existiera
        # la señal post_save de apps/users/signals.py pueden no tener
        # profile todavía -- en ese caso se asume el default (recibir
        # alertas) en vez de romper con AttributeError/RelatedObjectDoesNotExist.
        profile = getattr(saved_search.user, 'profile', None)
        if profile is not None and not profile.receive_email_alerts:
            skipped += 1
            continue

        # IMMEDIATE no lleva throttle a propósito (esa es su semántica: avisar
        # en cuanto haya resultados nuevos). DAILY y WEEKLY sí lo necesitan,
        # porque el beat pasa por aquí cada hora.
        min_hours_by_frequency = {
            SavedSearch.Frequency.DAILY: MIN_HOURS_BETWEEN_DAILY_ALERTS,
            SavedSearch.Frequency.WEEKLY: MIN_HOURS_BETWEEN_WEEKLY_ALERTS,
        }
        min_hours = min_hours_by_frequency.get(saved_search.frequency)
        if min_hours and saved_search.last_notified_at:
            elapsed = now - saved_search.last_notified_at
            if elapsed < timedelta(hours=min_hours):
                skipped += 1
                continue

        matches = saved_search.get_matches(since=saved_search.last_notified_at)
        match_ids = list(matches.values_list('pk', flat=True))
        if not match_ids:
            continue

        deliver_saved_search_alert.delay(saved_search.pk, match_ids)

        # Se actualiza aquí, en el dispatch, no dentro de la tarea de
        # envío: así, aunque el email tarde en salir de la cola o esté
        # reintentando por un fallo SMTP, no se vuelve a recalcular ni
        # duplicar ese mismo lote de matches en la siguiente pasada del
        # beat (cada hora).
        saved_search.last_notified_at = now
        saved_search.save(update_fields=['last_notified_at'])
        dispatched += 1

    logger.info('Alertas encoladas: %s. Búsquedas omitidas: %s.', dispatched, skipped)
    return {'dispatched': dispatched, 'skipped': skipped}
