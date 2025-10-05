# config/urls.py  ← 全文置き換え
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

from core.views import (
    DashboardView,
    MapView,
    UploadView,
    RecordsView,
    SignUpView,
)

urlpatterns = [
    # --- 画面系 ---
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("map/", MapView.as_view(), name="map"),
    path("upload/", UploadView.as_view(), name="upload"),
    path("records/", RecordsView.as_view(), name="records"),

    # --- 認証 ---
    path("signup/", SignUpView.as_view(), name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),

    # --- 管理・ヘルスチェック ---
    path("admin/", admin.site.urls),
    path("healthz", lambda r: HttpResponse("ok"), name="healthz"),

    # --- API（DRF） ---
    path("api/", include("core.urls")),
]
