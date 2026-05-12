"""
Django settings for TrackIt project.
"""

import os
from pathlib import Path
from celery.schedules import crontab

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-trackit-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get('DEBUG', True))

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    
    # Local
    'core',
    'api',
    'scheduler',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
        'DIRS': [BASE_DIR / 'templates'],
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

# Database
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'trackit'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# CORS
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# Celery configuration
# Build Redis URL from environment variables
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'

# Build broker URL with SSL support if needed
if REDIS_PASSWORD:
    redis_scheme = 'rediss' if REDIS_SSL else 'redis'
    redis_url = f'{redis_scheme}://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
else:
    redis_scheme = 'redis'
    redis_url = f'{redis_scheme}://{REDIS_HOST}:{REDIS_PORT}/0'

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', redis_url)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', "django-db")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Celery Beat Schedule
# Note: Times are in UTC. Adjust CELERY_TIMEZONE if needed.
# Set environment variables to override default times:
#   REMINDER_HOUR=18 (default, 6 PM UTC)
#   REPORT_HOUR=21 (default, 9 PM UTC)
REMINDER_HOUR = int(os.environ.get('REMINDER_HOUR', 19))
REMINDER_MINUTE = int(os.environ.get('REMINDER_MINUTE', 10))
REPORT_HOUR = int(os.environ.get('REPORT_HOUR', 19))
REPORT_MINUTE = int(os.environ.get('REPORT_MINUTE', 11))

# Calculate token validity duration (hours between reminder and report)
TOKEN_VALIDITY_HOURS = REPORT_HOUR - REMINDER_HOUR

CELERY_BEAT_SCHEDULE = {
    'hourly-snapshot-job': {
        'task': 'scheduler.tasks.hourly_snapshot_job',
        'schedule': crontab(minute=0),  # Run every hour at minute 0
        'options': {'queue': 'trackit'},
    },
    'reminder-job': {
        'task': 'scheduler.tasks.reminder_job',
        'schedule': crontab(hour=REMINDER_HOUR, minute=REMINDER_MINUTE),
        'options': {'queue': 'trackit'},
    },
    'report-job': {
        'task': 'scheduler.tasks.report_job',
        'schedule': crontab(hour=REPORT_HOUR, minute=REPORT_MINUTE),
        'options': {'queue': 'trackit'},
    },
    'cleanup-tokens': {
        'task': 'scheduler.tasks.cleanup_expired_tokens',
        'schedule': crontab(minute=0),  # Run every hour at minute 0
        'options': {'queue': 'trackit'},
    },
}

# Email configuration
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', "587"))
EMAIL_USE_TLS = bool(os.environ.get('EMAIL_USE_TLS', True))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@trackit.local')

# Jira configuration
JIRA_BASE_URL = os.environ.get('JIRA_BASE_URL', 'https://jira.company.com')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME', 'bot@company.com')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN', '')

# Microsoft Teams configuration (Incoming Webhook)
TEAMS_WEBHOOK_URL = os.environ.get('TEAMS_WEBHOOK_URL', '')
# Example: https://outlook.webhook.office.com/webhookb2/xxx@xxx/IncomingWebhook/xxx

# Site URL for links in notifications
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')


# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / '../logs' / 'trackit.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'trackit': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_SECURITY_POLICY = {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'"),
        'style-src': ("'self'", "'unsafe-inline'"),
    }
