# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Home / logout / healthz は config.views
from . import views

# 画面（ダッシュボード/マップ/サインアップ/アップロード）は core 側
from core.views import DashboardView, MapView, SignUpView, UploadView

# Django標準のログイン（ログアウトは自前ビューを使う）
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # API
    path("api/", include("core.urls")),

    # 認証（ユーザー用UI）
    path("signup/", SignUpView.as_view(), name="signup"),
    path("login/",  auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),  # ← ここを差し替え

    # ユーザー向け画面
    path("", views.HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("map/", MapView.as_view(), name="map"),
    path("upload/", UploadView.as_view(), name="upload"),

    path("healthz", views.healthz),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
