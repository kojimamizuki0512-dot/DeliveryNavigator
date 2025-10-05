#!/usr/bin/env bash
set -e

# Koyeb側で別の設定が刺さっていても、無ければ config.settings を使う
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings}"

# （必要な人だけ）Vision SA JSON を展開
if [ -n "$VISION_SA_JSON" ]; then
  echo "$VISION_SA_JSON" > /app/vision-sa.json
fi

# 静的ファイルとDB
python manage.py collectstatic --noinput
python manage.py migrate --noinput || true

# 起動
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
