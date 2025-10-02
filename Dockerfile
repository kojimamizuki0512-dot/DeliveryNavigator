# Pythonの軽量イメージ
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 依存とTesseract（日本語データ含む）をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-jpn \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 依存を入れる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# プロジェクト一式をコピー
COPY . .

# 本番設定とTesseractのパス
ENV DJANGO_SETTINGS_MODULE=config.settings_prod
ENV TESSERACT_CMD=/usr/bin/tesseract

# ポート公開
EXPOSE 8000

# 静的ファイル収集（初回失敗しても続行）
RUN python manage.py collectstatic --noinput || true

# サーバー起動
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120"]
