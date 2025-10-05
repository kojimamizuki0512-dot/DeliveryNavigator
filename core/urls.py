from django.urls import path
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
from .views_auth import SignupView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    # 認証
    path("accounts/login/",  auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
    path("accounts/signup/", SignupView.as_view(), name="signup"),
]
