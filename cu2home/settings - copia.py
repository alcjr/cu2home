import os
import configparser
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar .env -- PRIMERO, antes de cualquier os.getenv() que dependa de él.
# (Antes esto se cargaba después de los bloques de NPM/GDAL de abajo, así
# que esas variables siempre volvían vacías: bug real, corregido aquí.)
load_dotenv(BASE_DIR / '.env')

# ==================== RUTAS DE HERRAMIENTAS EXTERNAS (Windows/conda) ====================
# Antes hardcodeadas a "C:\Users\USER\..." -- rompía en cualquier máquina
# que no fuera la del desarrollador original, y romperá en despliegue
# (Linux/Docker). Ahora se leen de variables de entorno y solo se aplican
# si existen; en Linux/producción simplemente no se activan.
NPM_BIN_PATH = os.getenv('NPM_BIN_PATH', '')

node_path = os.getenv('NODE_PATH_WIN', '')
if node_path and os.path.exists(node_path):
    os.environ['PATH'] = node_path + os.pathsep + os.environ.get('PATH', '')

# ==================== CONFIGURACIÓN GDAL (necesaria para GeoDjango/PostGIS) ====================
# Antes se intentaba adivinar la ruta a partir de CONDA_PREFIX -- solo
# funciona si manage.py se lanza con el conda activado. El flujo real es
# (venv) normal de Python + GDAL viviendo en el env base de miniconda, así
# que ahora se leen rutas explícitas desde variables de entorno (.env).
# En Linux/producción (Docker), GDAL se instala vía paquetes del sistema
# (libgdal-dev / gdal-bin) y Django lo encuentra sin tocar nada de esto.
GDAL_LIBRARY_PATH = None  # setting real que lee django.contrib.gis.gdal

if os.name == 'nt':
    gdal_bin_dir = os.getenv('GDAL_BIN_DIR_WIN', '')
    if gdal_bin_dir and os.path.exists(gdal_bin_dir):
        os.environ['PATH'] = gdal_bin_dir + os.pathsep + os.environ.get('PATH', '')

    # OJO: GDAL_LIBRARY_PATH lo lee Django como SETTING propio
    # (settings.GDAL_LIBRARY_PATH), NO como variable de entorno del SO --
    # por eso va a una variable de módulo normal, no a os.environ.
    gdal_library_path = os.getenv('GDAL_LIBRARY_PATH_WIN', '')
    if gdal_library_path:
        GDAL_LIBRARY_PATH = gdal_library_path

    # GDAL_DATA y PROJ_LIB sí son variables de entorno reales que
    # consultan directamente las librerías GDAL/PROJ.
    gdal_data_path = os.getenv('GDAL_DATA_WIN', '')
    if gdal_data_path:
        os.environ['GDAL_DATA'] = gdal_data_path

    proj_lib_path = os.getenv('PROJ_LIB_WIN', '')
    if proj_lib_path:
        os.environ['PROJ_LIB'] = proj_lib_path

# Cargar config.ini
CONFIG_INI_PATH = BASE_DIR / 'config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_INI_PATH, encoding='utf-8')


def get_config(section, key, fallback=None):
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback


def get_config_boolean(section, key, fallback=False):
    try:
        return config.getboolean(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


def get_config_int(section, key, fallback=0):
    try:
        return config.getint(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


def get_config_float(section, key, fallback=0.0):
    try:
        return config.getfloat(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Database
# Motor confirmado: PostgreSQL. Se usa el backend PostGIS porque:
#  - models.py define Property.location como PointField (geolocalización real,
#    necesaria para la app `visor` / mapas de la arquitectura).
#  - settings.py ya trae toda la configuración de GDAL para Windows/conda,
#    lo que solo tiene sentido si se va a usar GeoDjango.
# Si el plan es NO usar PostGIS todavía, cambiar ENGINE a
# 'django.db.backends.postgresql' y quitar 'django.contrib.gis' de
# INSTALLED_APPS + el PointField en el modelo.
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME', 'cu2home_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.humanize',
    'django_htmx',
    # 'tailwind',
    # 'theme',
    'parler',
    'apps.core.apps.CoreConfig',
    'apps.properties',
    'apps.users',
    'apps.dashboard',
    'apps.search',
    'apps.authentication',
    # TODO: registrar cuando tengan modelos/migraciones listos para no
    # dejar tablas huérfanas a medio crear. Verificar el nombre real de
    # cada AppConfig en su apps.py antes de descomentar:
    # 'apps.config',
    # 'apps.visor',
]



USE_I18N = True
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.core.middleware.ActiveLanguageMiddleware',
]

ROOT_URLCONF = 'cu2home.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'apps.core.context_processors.site_settings',
                'apps.properties.context_processors.featured_properties',
            ],
        },
    },
]


WSGI_APPLICATION = 'cu2home.wsgi.application'

# --- Usuario ---
# Decisión: se mantiene el auth.User estándar de Django (sin AUTH_USER_MODEL
# custom). `users` (portal público) es un perfil OneToOne sobre auth.User.
# `authentication` (panel admin) NO tiene modelo propio: reutiliza auth.User
# con is_staff=True + StaffLoginForm/@staff_member_required. Esto evita
# duplicar hashing de contraseñas, gestión de sesión, etc.
LOGIN_URL = 'authentication:login'
LOGIN_REDIRECT_URL = '/'  # TODO: apuntar a 'dashboard:index' cuando exista esa vista
LOGOUT_REDIRECT_URL = 'authentication:login'

# Internationalization
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
USE_I18N = True
USE_L10N = True
USE_TZ = True
# Antes no estaba declarado -- Django caía en el default 'UTC' de forma
# implícita. Se hace explícito porque CELERY_TIMEZONE (más abajo) debe
# coincidir con este valor o los crontab() de CELERY_BEAT_SCHEDULE
# dispararán a la hora equivocada.
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')

# Static & Media
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Tailwind
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = ['127.0.0.1']

# Parler
PARLER_LANGUAGES = {
    None: ({'code': 'es'}, {'code': 'en'}),
    'default': {'fallback': 'es', 'hide_untranslated': False},
}

# Configuraciones desde config.ini
SITE_NAME = get_config('General', 'site_name', 'cu2home')
SITE_DESCRIPTION = get_config('General', 'site_description', 'Portal inmobiliario en Cuba')
SEARCH_ENGINE_HOST = get_config('Search', 'engine_host', 'http://localhost:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', '')
SEARCH_RESULTS_PER_PAGE = get_config_int('Search', 'results_per_page', 20)

TILE_LAYER_URL = get_config('Maps', 'tile_layer_url', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
TILE_LAYER_ATTRIBUTION = get_config('Maps', 'tile_layer_attribution', '© OpenStreetMap contributors')
DEFAULT_MAP_CENTER_LAT = get_config_float('Maps', 'default_center_lat', 23.0)
DEFAULT_MAP_CENTER_LNG = get_config_float('Maps', 'default_center_lng', -82.0)
DEFAULT_MAP_ZOOM = get_config_int('Maps', 'default_zoom', 7)

# Logging
LOG_LEVEL = get_config('Logging', 'nivel_desarrollo', 'DEBUG') if DEBUG else get_config('Logging', 'nivel_produccion', 'INFO')
LOG_FILE = BASE_DIR / 'logs' / get_config('Logging', 'log_file', 'cu2home.log')
LOG_MAX_BYTES = get_config_int('Logging', 'max_bytes', 10485760)
LOG_BACKUP_COUNT = get_config_int('Logging', 'backup_count', 10)

# Asegura que exista logs/ antes de que RotatingFileHandler intente abrir
# el fichero -- si el directorio no existe, Django falla al arrancar.
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'}},
    'handlers': {
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE,
            'maxBytes': LOG_MAX_BYTES,
            'backupCount': LOG_BACKUP_COUNT,
            'formatter': 'verbose',
        },
        'console': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['file', 'console'], 'level': LOG_LEVEL},
}

# Email
# Backend explícito: antes no estaba declarado y Django usa por defecto
# 'django.core.mail.backends.smtp.EmailBackend', que SÍ es lo que
# queremos -- pero dejarlo implícito hacía fácil que alguien en local
# terminara enviando emails reales sin darse cuenta. En desarrollo se
# puede sobrescribir con EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# en el .env para volcar los correos a la consola en vez de enviarlos.
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = get_config('Email', 'smtp_server', '')
EMAIL_PORT = get_config_int('Email', 'smtp_port', 465)
EMAIL_USE_TLS = get_config_boolean('Email', 'smtp_use_tls', True)
EMAIL_HOST_USER = get_config('Email', 'smtp_user', '')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', '')
# Antes no existía: send_mail(from_email=None) en send_saved_search_alerts
# caía en el default de Django 'webmaster@localhost', que la mayoría de
# proveedores SMTP rechaza o marca como spam. Se usa el propio buzón SMTP
# como remitente por defecto, pero permite override explícito por env.
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@cu2home.com')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== CELERY (broker: Redis) ====================
# Nada de esto existía antes -- el paquete `celery` solo estaba instalado
# como dependencia transitiva en el venv, sin `cu2home/celery.py` ni
# CELERY_* aquí. Redis se usa tanto de broker como de result backend
# (más simple que RabbitMQ para un solo VPS/contenedor; si el volumen de
# tareas crece y se necesita AMQP con confirmaciones más estrictas,
# CELERY_BROKER_URL es lo único que habría que cambiar).
#
# En Linux/producción, REDIS_URL se define en el .env real, no en éste;
# en local con `docker run -p 6379:6379 redis` o un Redis nativo instalado
# basta con el fallback de abajo.
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
# Alineado con TIME_ZONE de arriba -- si no coinciden, los crontab() de
# CELERY_BEAT_SCHEDULE se calculan sobre UTC aunque TIME_ZONE sea otro,
# y las alertas "diarias" saldrían a una hora distinta a la esperada.
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Resultados de tareas: se guardan 1 día, suficiente para depurar un envío
# fallido sin acumular basura indefinidamente en Redis.
CELERY_RESULT_EXPIRES = 60 * 60 * 24

# Reintentos por defecto para cualquier tarea que no fije los suyos propios
# (deliver_saved_search_alert, en apps/users/tasks.py, sí los fija de forma
# más específica para fallos SMTP).
CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

# Apagado por defecto (comportamiento async real, como en producción).
# Se activa solo poniendo CELERY_TASK_ALWAYS_EAGER=True en el .env local
# para poder probar `manage.py send_saved_search_alerts` sin tener que
# levantar un worker aparte -- en modo eager, .delay() ejecuta la tarea
# en el momento, dentro del mismo proceso, saltándose Redis por completo.
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'

# Beat: sustituye al cron externo que antes lanzaba
# `manage.py send_saved_search_alerts`. Se ejecuta cada hora -- la propia
# tarea sigue respetando MIN_HOURS_BETWEEN_DAILY_ALERTS para no duplicar
# los avisos "daily"; los "immediate" sí se comprueban en cada pasada.
CELERY_BEAT_SCHEDULE = {
    'dispatch-saved-search-alerts': {
        'task': 'apps.users.tasks.dispatch_saved_search_alerts',
        'schedule': 60 * 60,  # cada hora, en segundos
    },
}

MAX_IMAGES_PER_PROPERTY = get_config_int('Properties', 'max_images_per_property', 10)