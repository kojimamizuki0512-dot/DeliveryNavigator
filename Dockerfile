# できるだけ軽く・確実に
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 画像まわりで Pillow が困らないよう最小パッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    libjpeg62-turbo-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# 依存を先に入れる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . .

# entrypoint 実行権限
RUN chmod +x /app/entrypoint.sh

# ポート（Koyebは環境変数PORTを渡すので露出は任意）
EXPOSE 8000

CMD ["./entrypoint.sh"]
