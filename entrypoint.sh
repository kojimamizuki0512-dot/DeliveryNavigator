#!/usr/bin/env bash
set -e

# 環境変数のデフォルトを補完
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_prod}"
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"

# Render が渡す PORT を使う（なければ 8000）
PORT="${PORT:-8000}"

# マイグレーション & 静的ファイル収集
python manage.py migrate --noinput || true
python manage.py collectstatic --noinput || true

# Gunicorn 起動
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2
