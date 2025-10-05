#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] start"

# --- Google Vision の鍵を /app/vision-sa.json に書き出す ---
if [[ -n "${VISION_SA_JSON_B64:-}" ]]; then
  echo "$VISION_SA_JSON_B64" | base64 -d > /app/vision-sa.json
  chmod 600 /app/vision-sa.json
  echo "[entrypoint] wrote /app/vision-sa.json from base64"
elif [[ -n "${VISION_SA_JSON:-}" ]]; then
  printf "%s" "$VISION_SA_JSON" > /app/vision-sa.json
  chmod 600 /app/vision-sa.json
  echo "[entrypoint] wrote /app/vision-sa.json"
fi

# --- Django 標準の起動手順 ---
echo "[entrypoint] migrate..."
python manage.py migrate --noinput

echo "[entrypoint] collectstatic..."
python manage.py collectstatic --noinput

echo "[entrypoint] gunicorn start"
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 3
