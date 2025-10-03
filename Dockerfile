# 1) 軽量Python
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 2) 必要パッケージ（Tesseract含む）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# 3) 作業ディレクトリ
WORKDIR /app

# 4) 先に依存だけコピー＆インストール
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5) ソースコード
COPY . /app

# 6) エントリポイント（実行権限）
RUN chmod +x /app/entrypoint.sh

# 7) ポート（KoyebはPORT環境変数を渡してくる）
EXPOSE 8000

# 8) 起動
CMD ["/app/entrypoint.sh"]
