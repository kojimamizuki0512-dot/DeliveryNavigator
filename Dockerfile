FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OS パッケージ（tesseract を含む）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libtesseract-dev ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Cloud Run が PORT を注入 -> entrypoint.sh が $PORT で待ち受け
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
