"""Настройки для запуска в Docker и на сервере."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = False

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32 or SECRET_KEY.startswith(('django-insecure', 'replace-with')):
    raise ImproperlyConfigured('Задайте надёжный DJANGO_SECRET_KEY (от 32 символов) в .env')

# Статика отдаётся через WhiteNoise со сжатием и хешами в именах файлов
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Включается, когда сайт работает за HTTPS (например, за nginx с сертификатом)
if env_bool('DJANGO_HTTPS', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
