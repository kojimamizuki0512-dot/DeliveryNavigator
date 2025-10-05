#!/usr/bin/env bash
set -e

# 必要なら Vision 用のJSONを展開
if [ -n "$VISION_SA_JSON" ]; then
  echo "$VISION_SA_JSON" > /app/vision-sa.json
fi

# 静的ファイルを集める（これが無いと本番でCSSが出ません）
python manage.py collectstatic --noinput

# マイグレーション（必要なら。既にやっているなら残してOK）
python manage.py migrate --noinput || true

# 起動
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
