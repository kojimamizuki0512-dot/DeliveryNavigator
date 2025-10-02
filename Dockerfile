#!/usr/bin/env bash
set -e
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_prod}"
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2
