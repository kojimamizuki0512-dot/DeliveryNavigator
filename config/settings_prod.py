# config/settings_prod.py
from .settings import *  # ベース設定を継承
import os
import dj_database_url

DEBUG = False

# ----- Host / CSRF -----
# 例: ALLOWED_HOSTS="*.koyeb.app,dreadful-kathe-kojima0512-28f81477.koyeb.app"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]

# 例: CSRF_TRUSTED_ORIGINS="https://*.koyeb.app,https://dreadful-kathe-kojima0512-28f81477.koyeb.app"
# ※ 末尾のスラッシュは入れない（https://.../ ← NG）
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# ----- HTTPS (Koyebのプロキシ越し) -----
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ----- 本番でだけ追加するアプリ/ミドルウェア -----
# requirements.txt に `django-cors-headers` と `whitenoise` を入れておくこと
INSTALLED_APPS += [
    "corsheaders",
]

# WhiteNoise で静的ファイルを配信（Gunicorn直下）
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + MIDDLEWARE

# （必要になったときだけ）CORSを広げたい場合は環境変数でONにする
# KOYEBの「Environment variables」で CORS_ALLOW_ALL_ORIGINS=true を入れると有効化
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"

# ----- Database（NeonなどのPostgres推奨 / 無ければsqliteにフォールバック）-----
DATABASES["default"] = dj_database_url.config(
    env="DATABASE_URL",
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
)

# ----- Static / Media -----
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ----- DRF 認証 -----
# simplejwt を使うなら requirements.txt に djangorestframework-simplejwt を入れておく
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",
)
