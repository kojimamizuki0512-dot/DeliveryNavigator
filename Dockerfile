FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings  # ← 本番もこれを使う

WORKDIR /app

# Pillowが困らない最小ライブラリ
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    libjpeg62-turbo-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# 依存インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . .

# entrypoint 実行権限
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
