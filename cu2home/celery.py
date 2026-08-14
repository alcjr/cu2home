import os

from celery import Celery

# Igual que manage.py: hay que fijar DJANGO_SETTINGS_MODULE antes de tocar
# nada de Django, para que Celery (worker o beat, lanzados como procesos
# aparte de manage.py) sepan qué settings cargar.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cu2home.settings')

app = Celery('cu2home')

# namespace='CELERY': todas las settings relevantes en settings.py deben
# llevar el prefijo CELERY_ (CELERY_BROKER_URL, CELERY_TASK_SERIALIZER...)
# en vez de nombres sueltos como BROKER_URL. Ya es así en el bloque nuevo
# de settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Busca un módulo tasks.py dentro de cada entrada de INSTALLED_APPS
# (apps.properties.tasks, apps.users.tasks, etc.) y registra ahí las
# tareas con @shared_task, sin tener que importarlas a mano una por una.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarea mínima para verificar que un worker está vivo y consumiendo
    de la cola correcta: `python manage.py shell -c
    "from cu2home.celery import debug_task; debug_task.delay()"`
    y comprobar el log del worker."""
    print(f'Request: {self.request!r}')
