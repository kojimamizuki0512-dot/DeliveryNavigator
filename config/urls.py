from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

from core.views import DashboardView, MapView, UploadView, RecordsView
from core.views_auth import SignupView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("map/", MapView.as_view(), name="map"),
    path("upload/", UploadView.as_view(), name="upload"),
    path("records/", RecordsView.as_view(), name="records"),

    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),

    path("admin/", admin.site.urls),
    path("healthz", lambda r: HttpResponse("ok"), name="healthz"),

    path("api/", include("core.urls")),   # 既存のAPIがあればここで
]
