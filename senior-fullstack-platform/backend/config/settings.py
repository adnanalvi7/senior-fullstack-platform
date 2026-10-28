import os
import sys
from pathlib import Path
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name, default):
    return os.environ.get(name, str(default)).lower() in ('true', '1', 'yes')


TESTING = 'test' in sys.argv or any('pytest' in arg for arg in sys.argv) or env_bool('DJANGO_TESTING', False)

# Secure by default: DEBUG must be switched on explicitly (docker-compose does so for the demo).
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not (DEBUG or TESTING):
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.')
    SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production-capex-platform'  # noqa: S105 (DEBUG/tests only)

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,backend').split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',

    # Local apps
    'apps.accounts',
    'apps.properties',
    'apps.projects',
    'apps.approvals',
    'apps.analytics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database configuration
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite')
if DB_ENGINE == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'capex_db'),
            'USER': os.environ.get('POSTGRES_USER', 'capex_user'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'capex_pass'),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'common.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'common.exceptions.custom_exception_handler',
}

# SimpleJWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS: the SPA is served same-origin through the Vite proxy; allow only configured origins.
CORS_ALLOWED_ORIGINS = [o for o in os.environ.get(
    'CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o]
CORS_ALLOW_CREDENTIALS = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'plain': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
}

# --------------------------------------------------------------------------------------
# Redis: three logical databases so that cache maintenance can never touch the Celery
# broker or the Channels layer (and vice versa).
#   /0 Celery broker + results   /1 analytics cache   /2 Channels layer
# --------------------------------------------------------------------------------------
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


def _redis_db(url, db):
    return f"{url.rsplit('/', 1)[0]}/{db}" if url.count('/') >= 3 else f"{url.rstrip('/')}/{db}"


# In-memory backends are an explicit choice (tests, or USE_REDIS=false for Redis-less local
# dev), never a silent fallback decided by probing the network at import time.
USE_REDIS = env_bool('USE_REDIS', True) and (not TESTING or env_bool('TEST_WITH_REDIS', False))

if USE_REDIS:
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ.get('REDIS_CACHE_URL', _redis_db(REDIS_URL, 1)),
            'TIMEOUT': 1800,
            'KEY_PREFIX': 'capex',
            # Fail fast: a Redis outage must degrade to "cache miss", not stall requests.
            'OPTIONS': {'socket_connect_timeout': 1, 'socket_timeout': 1, 'retry': Retry(NoBackoff(), 0)},
        }
    }
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [{
                'address': os.environ.get('CHANNELS_REDIS_URL', _redis_db(REDIS_URL, 2)),
                'socket_connect_timeout': 1,
            }]},
        },
    }
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'capex-locmem', 'TIMEOUT': 1800}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', _redis_db(REDIS_URL, 0))
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', _redis_db(REDIS_URL, 0))
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_RESULT_EXPIRES = 3600
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = not USE_REDIS or env_bool('CELERY_ALWAYS_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = TESTING
# Publishing happens in request threads (on commit): never block a request on a dead broker.
# A failed publish is safe because the PendingRollup outbox row is swept by beat.
CELERY_TASK_PUBLISH_RETRY = False
# Results are never read; not subscribing to the result backend keeps .delay() from blocking
# on result-backend reconnects when Redis is unavailable.
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_TRANSPORT_OPTIONS = {'socket_connect_timeout': 2, 'socket_timeout': 5, 'max_retries': 0}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
    'sweep-pending-rollups': {
        'task': 'apps.analytics.tasks.sweep_pending_rollups',
        'schedule': float(os.environ.get('ROLLUP_SWEEP_SECONDS', '60')),
    },
}
