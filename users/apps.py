"""Конфигурация приложения users."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Клиенты."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'Клиенты'
