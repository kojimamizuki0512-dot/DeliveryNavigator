#!/usr/bin/env bash
set -e

# Google Vision 用のJSON展開（必要な場合だけ）
if [ -n "$VISION_SA_JSON" ]; then
  echo "$VISION_SA_JSON" > /app/vision-sa.json
fi

# ★これが無いと本番でCSSが配信されません
python manage.py collectstatic --noinput

# 起動
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
