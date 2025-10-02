#!/usr/bin/env bash
set -e

# ====== 基本の環境 ======
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_prod}"
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"
PORT="${PORT:-8000}"

# ====== マイグレーション & 静的ファイル ======
python manage.py migrate --noinput || true
python manage.py collectstatic --noinput || true

# ====== 管理ユーザーの自動作成（Shell不要）======
# Render の Environment に以下を設定すると自動作成されます。
#   DJANGO_SUPERUSER_USERNAME
#   DJANGO_SUPERUSER_PASSWORD
#   DJANGO_SUPERUSER_EMAIL (任意)
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "Ensuring superuser '${DJANGO_SUPERUSER_USERNAME}' exists..."
  python manage.py createsuperuser \
    --noinput \
    --username "$DJANGO_SUPERUSER_USERNAME" \
    --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

# ====== 一回だけ任意の manage.py を実行したいとき（任意）======
# Environment に RUN_MANAGE_CMD="loaddata sample.json" のように入れてデプロイ。
# 動いたら RUN_MANAGE_CMD を消して再デプロイすればOK。
if [ -n "${RUN_MANAGE_CMD:-}" ]; then
  echo "Running one-off command: ${RUN_MANAGE_CMD}"
  python manage.py ${RUN_MANAGE_CMD} || true
fi

# ====== アプリ起動 ======
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2
