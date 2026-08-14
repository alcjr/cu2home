from django.core.management.base import BaseCommand

from apps.users.tasks import dispatch_saved_search_alerts

# La lógica de envío vive ahora en apps/users/tasks.py (dispatch_saved_search_alerts
# + deliver_saved_search_alert), como tareas de Celery. Este comando ya NO
# hace el trabajo directamente: solo dispara el orquestador.
#
# Se llama a dispatch_saved_search_alerts() como función normal (SIN
# .delay()): las tareas de Celery decoradas con @shared_task siguen
# siendo funciones Python normales si se invocan sin .delay()/
# .apply_async(). Por eso la PARTE DE DECISIÓN (qué SavedSearch tiene
# resultados nuevos, actualizar last_notified_at) se ejecuta siempre
# in-process, sin depender de ningún worker.
#
# OJO -- lo que SÍ requiere un worker de Celery corriendo
# (`celery -A cu2home worker -l info`) es el ENVÍO real: dentro de
# dispatch_saved_search_alerts() cada alerta se encola con
# deliver_saved_search_alert.delay(...), que es async de verdad. Sin
# worker consumiendo la cola de Redis, ese .delay() dejará la tarea
# encolada indefinidamente y el email NUNCA saldrá, aunque este comando
# termine con éxito y reporte "Alertas encoladas: N". Para probar en
# local sin levantar un worker aparte, poner
# CELERY_TASK_ALWAYS_EAGER=True en el entorno (Celery ejecuta la tarea
# en el momento, sin pasar por Redis).
#
# Si en producción hay un worker + beat corriendo, este comando deja de
# ser necesario en el cron -- CELERY_BEAT_SCHEDULE ya dispara
# dispatch_saved_search_alerts cada hora automáticamente. Se conserva
# solo como vía manual (`manage.py send_saved_search_alerts`) para forzar
# un envío inmediato sin esperar al siguiente tick del beat (el worker
# sigue haciendo falta igualmente para que ese envío se procese).


class Command(BaseCommand):
    help = (
        'Dispara manualmente el envío de alertas de SavedSearch activas '
        '(equivalente a esperar al siguiente tick de CELERY_BEAT_SCHEDULE). '
        'Si hay un worker de Celery corriendo, deliver_saved_search_alert se '
        'encola y se envía de forma asíncrona con reintentos; si no hay '
        'worker, se ejecuta igualmente pero de forma síncrona en este mismo '
        'proceso (delay() sin worker consumidor simplemente deja la tarea '
        'en la cola de Redis sin ejecutar -- para pruebas locales sin '
        'worker, usar CELERY_TASK_ALWAYS_EAGER=True en el .env).'
    )

    def handle(self, *args, **options):
        result = dispatch_saved_search_alerts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas encoladas: {result['dispatched']}. "
                f"Búsquedas omitidas: {result['skipped']}."
            )
        )
