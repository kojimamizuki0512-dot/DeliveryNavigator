# config/settings_prod.py
import os
from .settings import *

# dj_database_url はローカル未導入だと Pylance が赤くするので try に
try:
    import dj_database_url  # type: ignore
except Exception:  # 実行時に未使用なら問題なし
    dj_database_url = None  # type: ignore

# ---- 基本 ----
DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h.strip()
]

# ---- DB: DATABASE_URL があれば Postgres に切替 ----
if dj_database_url and "DATABASE_URL" in os.environ:
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=False
    )

# ---- 静的/メディア（Render の永続ディスク /data を想定）----
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/data/static")
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/data/media")

# ---- WhiteNoise（静的ファイル配信）----
# base settings で STORAGES が無いケースに備えてフォールバックを定義
if "STORAGES" not in globals():
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }

# WhiteNoise ミドルウェアを先頭の次に差し込む
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# WhiteNoise 用ストレージ
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
# 互換目的で STATICFILES_STORAGE も明示（なくてもOKだが警告避けに有益）
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]

# ---- CORS/CSRF ----
CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = []
for h in ALLOWED_HOSTS:
    if not h or h == "*":
        continue
    if h.startswith("http"):
        CSRF_TRUSTED_ORIGINS.append(h)
    else:
        CSRF_TRUSTED_ORIGINS.append(f"https://{h}")

# ---- Tesseract（Docker/Render のパス）----
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract")

# ---- ログ（ざっくり）----
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
