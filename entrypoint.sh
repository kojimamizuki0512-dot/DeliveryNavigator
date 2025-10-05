#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "[entrypoint] migrate..."
python manage.py migrate --noinput

echo "[entrypoint] collectstatic..."
python manage.py collectstatic --noinput

# optional: 一度だけ実行したい manage.py コマンド
if [[ -n "${RUN_MANAGE_CMD:-}" ]]; then
  echo "[entrypoint] RUN_MANAGE_CMD=${RUN_MANAGE_CMD}"
  python manage.py ${RUN_MANAGE_CMD} || true
  export RUN_MANAGE_CMD=""
fi

# ★ ここが今回のポイント：MEDIA_ROOT を作る
mkdir -p "${MEDIA_ROOT:-/tmp/dn_media}"

echo "[entrypoint] gunicorn start"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${GUNICORN_WORKERS:-3} \
  --threads ${GUNICORN_THREADS:-3} \
  --timeout ${GUNICORN_TIMEOUT:-60}
