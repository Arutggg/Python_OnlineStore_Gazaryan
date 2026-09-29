FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=online_store.settings.production

WORKDIR /app

# Зависимости ставятся отдельным слоем: при правке кода они не переустанавливаются
COPY requirements.txt /app/
RUN python -m pip install -r requirements.txt

COPY . /app/

# Статика собирается на этапе сборки. Миграции требуют запущенной БД,
# поэтому они выполняются при старте контейнера (docker/entrypoint.sh).
RUN DJANGO_SECRET_KEY=collectstatic-only-build-time-key-0123456789abcdef \
    python manage.py collectstatic --no-input \
    && mkdir -p /app/media \
    && useradd --system --create-home app \
    && chown -R app:app /app/media \
    && chmod +x /app/docker/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "online_store.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
