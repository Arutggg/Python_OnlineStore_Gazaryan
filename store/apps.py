"""Конфигурация приложения store."""

from django.apps import AppConfig


class StoreConfig(AppConfig):
    """Магазин."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'
    verbose_name = 'Магазин'
