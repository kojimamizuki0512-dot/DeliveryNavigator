#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] boot start"

# --- Google Vision: 1行JSON → ファイル化 ---
# 例）環境変数で:
#   GOOGLE_APPLICATION_CREDENTIALS=/app/vision-sa.json
#   VISION_SA_JSON={"type":"service_account",...}  ←1行JSON
if [[ -n "${VISION_SA_JSON:-}" && -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "[entrypoint] writing Vision credentials to ${GOOGLE_APPLICATION_CREDENTIALS}"
  # そのまま書き出し（\n は JSON の中でエスケープとして扱われるのでOK）
  printf '%s' "${VISION_SA_JSON}" > "${GOOGLE_APPLICATION_CREDENTIALS}"
  chmod 600 "${GOOGLE_APPLICATION_CREDENTIALS}"
else
  echo "[entrypoint] Vision env not set (VISION_SA_JSON or GOOGLE_APPLICATION_CREDENTIALS missing)"
fi

# --- Django migrate ---
echo "[entrypoint] migrate..."
python manage.py migrate --noinput

# --- collectstatic ---
echo "[entrypoint] collectstatic..."
python manage.py collectstatic --noinput

# --- one-shot manage command（必要なら）---
if [[ -n "${RUN_MANAGE_CMD:-}" ]]; then
  echo "[entrypoint] RUN_MANAGE_CMD=${RUN_MANAGE_CMD}"
  python manage.py ${RUN_MANAGE_CMD} || true
  export RUN_MANAGE_CMD=""
fi

# --- gunicorn ---
echo "[entrypoint] gunicorn start"
# ワーカー数は Free だと少なめでOK
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --threads 2 \
  --timeout 90
