FROM python:3.11-slim

# 必要パッケージ（tesseract を含む）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 依存インストール
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . /app/

# エントリポイント
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
