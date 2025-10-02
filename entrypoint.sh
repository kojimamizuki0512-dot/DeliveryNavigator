#!/usr/bin/env bash
set -e

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_prod}"
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"
PORT="${PORT:-8000}"

python manage.py migrate --noinput || true
python manage.py collectstatic --noinput || true

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "Ensuring superuser '${DJANGO_SUPERUSER_USERNAME}' exists..."
  python manage.py createsuperuser \
    --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

if [ -n "${RUN_MANAGE_CMD:-}" ]; then
  echo "Running one-off command: ${RUN_MANAGE_CMD}"
  python manage.py ${RUN_MANAGE_CMD} || true
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2
