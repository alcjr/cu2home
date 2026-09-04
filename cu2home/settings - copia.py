import os
import configparser
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar .env -- PRIMERO, antes de cualquier os.getenv() que dependa de él.
load_dotenv(BASE_DIR / '.env')

# ==================== RUTAS DE HERRAMIENTAS EXTERNAS (Windows/conda) ====================
NPM_BIN_PATH = os.getenv('NPM_BIN_PATH', '')

node_path = os.getenv('NODE_PATH_WIN', '')
if node_path and os.path.exists(node_path):
    os.environ['PATH'] = node_path + os.pathsep + os.environ.get('PATH', '')

# ==================== CONFIGURACIÓN GDAL (necesaria para GeoDjango/PostGIS) ====================
GDAL_LIBRARY_PATH = None

if os.name == 'nt':
    gdal_bin_dir = os.getenv('GDAL_BIN_DIR_WIN', '')
    if gdal_bin_dir and os.path.exists(gdal_bin_dir):
        os.environ['PATH'] = gdal_bin_dir + os.pathsep + os.environ.get('PATH', '')

    gdal_library_path = os.getenv('GDAL_LIBRARY_PATH_WIN', '')
    if gdal_library_path:
        GDAL_LIBRARY_PATH = gdal_library_path

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
    'parler',
    'apps.core.apps.CoreConfig',
    'apps.properties',
    'apps.users',
    'apps.dashboard',
    'apps.authentication',
    'apps.visor',
    'apps.config',
]

# ==================== INTERNATIONALIZATION ====================
# Configuración única y limpia
USE_I18N = True
USE_L10N = True
USE_TZ = True
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')

# Idioma por defecto
LANGUAGE_CODE = 'es'

# Idiomas disponibles
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
]

# Ruta de archivos de traducción
LOCALE_PATHS = [BASE_DIR / 'locale']

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # Importante: después de SessionMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    # El middleware de idioma activo se ha comentado porque podría forzar el idioma
    # 'apps.core.middleware.ActiveLanguageMiddleware',
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
                'django.template.context_processors.i18n',  # Para {% trans %} en templates
                'apps.core.context_processors.site_settings',
                'apps.properties.context_processors.featured_properties',
            ],
        },
    },
]


WSGI_APPLICATION = 'cu2home.wsgi.application'

# --- Usuario ---
LOGIN_URL = 'authentication:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'authentication:login'

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
# --- Ruta del archivo de log (robusta ante rutas duplicadas en config.ini) ---
_log_file_raw = get_config('Logging', 'log_file', 'cu2home.log')
# Extraer solo el nombre del archivo para evitar rutas anidadas tipo logs/cu2home/logs/cu2home.log
_log_file_name = os.path.basename(_log_file_raw.replace('\\', '/').replace('//', '/')) or 'cu2home.log'
LOG_FILE = BASE_DIR / 'logs' / _log_file_name

# Asegurar que el directorio de logs exista ANTES de que Django configure el handler
os.makedirs(LOG_FILE.parent, exist_ok=True)
LOG_MAX_BYTES = get_config_int('Logging', 'max_bytes', 10485760)
LOG_BACKUP_COUNT = get_config_int('Logging', 'backup_count', 10)

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
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = get_config('Email', 'smtp_server', '')
EMAIL_PORT = get_config_int('Email', 'smtp_port', 465)
EMAIL_HOST_USER = get_config('Email', 'smtp_user', '')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@cu2home.com')

# EMAIL_USE_TLS (STARTTLS, típico en el puerto 587) y EMAIL_USE_SSL (SSL
# implícito, típico en el puerto 465) son mutuamente excluyentes en Django
# -- activar ambos, o activar el que no corresponde al puerto, deja la
# conexión SMTP colgada hasta el timeout (o un SSLError tras un buen rato)
# sin ningún error visible en el navegador, porque el fallo ocurre dentro
# de smtplib mientras la request sigue "cargando". config.ini traía
# smtp_port=465 con smtp_use_tls=true, que es justo esa combinación
# incorrecta. Se deriva automáticamente por puerto en vez de depender de
# smtp_use_tls para el caso 465, que ahora se ignora a propósito.
if EMAIL_PORT == 465:
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
else:
    EMAIL_USE_TLS = get_config_boolean('Email', 'smtp_use_tls', True)
    EMAIL_USE_SSL = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== CELERY ====================
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

CELERY_RESULT_EXPIRES = 60 * 60 * 24

CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'

CELERY_BEAT_SCHEDULE = {
    'dispatch-saved-search-alerts': {
        'task': 'apps.users.tasks.dispatch_saved_search_alerts',
        'schedule': 60 * 60,
    },
    'dispatch-favorite-change-alerts': {
        'task': 'apps.users.tasks.dispatch_favorite_change_alerts',
        'schedule': 60 * 60,
    },
}

MAX_IMAGES_PER_PROPERTY = get_config_int('Properties', 'max_images_per_property', 10)

# ==================== MONEDA ====================
CURRENCY_CODE = get_config('Currency', 'code', 'USD')
CURRENCY_SYMBOL = get_config('Currency', 'symbol', '$')
CURRENCY_DECIMAL_PLACES = get_config_int('Currency', 'decimal_places', 2)
CURRENCY_THOUSANDS_SEP = get_config('Currency', 'thousands_separator', '.')
CURRENCY_DECIMAL_SEP = get_config('Currency', 'decimal_separator', ',')
CURRENCY_SYMBOL_POSITION = get_config('Currency', 'symbol_position', 'before_attached')