# config/settings_prod.py
from .settings import *  # ベース設定を継承
import os
import dj_database_url

DEBUG = False

# ----- Host / CSRF -----
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
# 例: "*.koyeb.app,dreadful-kathe-kojima0512-28f81477.koyeb.app"

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
# 例: "https://*.koyeb.app,https://dreadful-kathe-kojima0512-28f81477.koyeb.app"

# Koyeb(プロキシ)越しHTTPSを正しく検知する
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True  # http -> https リダイレクト

# クッキーは常にHTTPSのみで送る
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ----- Database（Neon などの Postgres を推奨 / 無ければ sqlite フォールバック）-----
DATABASES["default"] = dj_database_url.config(
    env="DATABASE_URL",
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
)

# ----- Static / Media -----
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

# （任意）REST Framework認証の併用
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",
)
