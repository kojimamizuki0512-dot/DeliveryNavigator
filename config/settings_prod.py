# config/settings_prod.py
from .settings import *  # ベース設定を継承
import os
import dj_database_url

DEBUG = False

# ----- Host / CSRF -----
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# ----- HTTPS (Koyeb のプロキシ越し) -----
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ===== corsheaders を重複させない / 先頭に置く =====
INSTALLED_APPS = [
    a for a in INSTALLED_APPS
    if not (a == "corsheaders" or a.startswith("corsheaders."))
]
INSTALLED_APPS.append("corsheaders")

MIDDLEWARE = [
    m for m in MIDDLEWARE
    if not (m == "corsheaders.middleware.CorsMiddleware" or m.startswith("corsheaders."))
]
MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

# 環境変数で一時的に全開放したい場合のみ true
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"

# ===== WhiteNoise（静的ファイル配信）=====
whitenoise_mw = "whitenoise.middleware.WhiteNoiseMiddleware"
if whitenoise_mw not in MIDDLEWARE:
    try:
        sec_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1
    except ValueError:
        sec_idx = 0
    MIDDLEWARE.insert(sec_idx, whitenoise_mw)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ===== Database（Neon 想定：SSL強制）=====
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=True,  # ★ 重要：Neon で sslmode=require を強制
    )
}

# ===== DRF 認証 =====
REST_FRAMEWORK = globals().get("REST_FRAMEWORK", {})
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",
)

# ===== Logging（本番で500のスタックを確実に出す）=====
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.template": {"handlers": ["console"], "level": "WARNING"},
        "django.db.backends": {"handlers": ["console"], "level": os.getenv("DJANGO_DB_LOG_LEVEL", "WARNING")},
    },
}
