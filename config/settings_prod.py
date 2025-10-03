# config/settings_prod.py
from .settings import *  # ベース設定を継承
import os
import dj_database_url

DEBUG = False

# ----- Host / CSRF -----
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]

# 末尾スラッシュ不要
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# ----- HTTPS (Koyebのプロキシ越し) -----
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ===== 正規化: corsheaders を重複させない =====
# INSTALLED_APPS から corsheaders 系の表記を一度すべて除去し、1つだけ追加
INSTALLED_APPS = [
    a for a in INSTALLED_APPS
    if not (a == "corsheaders" or a.startswith("corsheaders."))
]
INSTALLED_APPS.append("corsheaders")

# MIDDLEWARE も同様に正規化し、CORS を先頭へ
MIDDLEWARE = [
    m for m in MIDDLEWARE
    if not (m == "corsheaders.middleware.CorsMiddleware" or m.startswith("corsheaders."))
]
MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

# ===== WhiteNoise（静的ファイルをアプリで配信）=====
whitenoise_mw = "whitenoise.middleware.WhiteNoiseMiddleware"
if whitenoise_mw not in MIDDLEWARE:
    try:
        sec_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1
    except ValueError:
        sec_idx = 0
    MIDDLEWARE.insert(sec_idx, whitenoise_mw)

# （必要時のみ）CORS 全開放を環境変数でONにできる
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"

# ----- Database（Neon推奨 / 無ければsqliteフォールバック）-----
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

# ----- DRF 認証（simplejwt を使うなら requirements.txt に入っていればOK）-----
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.SessionAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",
)
