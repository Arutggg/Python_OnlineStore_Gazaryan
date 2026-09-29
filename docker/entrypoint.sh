#!/bin/sh
# Подготовка контейнера перед запуском веб-сервера.
set -e

echo "Ожидание базы данных ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os
import sys
import time

import psycopg

params = dict(
    host=os.getenv('DB_HOST', 'db'), port=os.getenv('DB_PORT', '5432'),
    dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
)
for _ in range(30):
    try:
        psycopg.connect(**params, connect_timeout=2).close()
        sys.exit(0)
    except psycopg.OperationalError:
        time.sleep(1)
sys.exit('База данных недоступна')
PY

python manage.py migrate --no-input

if [ "${LOAD_DEMO_DATA:-0}" = "1" ]; then
    python manage.py load_goods --if-empty
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME}" ]; then
    python manage.py createsuperuser --no-input 2>/dev/null \
        && echo "Создан суперпользователь ${DJANGO_SUPERUSER_USERNAME}" \
        || echo "Суперпользователь ${DJANGO_SUPERUSER_USERNAME} уже существует"
fi

exec "$@"
