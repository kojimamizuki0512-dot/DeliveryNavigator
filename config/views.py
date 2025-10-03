# config/views.py
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.contrib.auth import logout
from django.shortcuts import redirect
# from django.db import connections  # DBチェック版にするなら使用

class HomeView(TemplateView):
    template_name = "home.html"

def logout_view(request):
    """
    GETでログアウト→ホームに戻す（Django5のLogoutViewはPOST専用のため）
    """
    logout(request)
    return redirect("home")

def healthz(request):
    # 軽量版（必要ならDB疎通チェックに差し替え可）
    # with connections["default"].cursor() as cur: cur.execute("SELECT 1;")
    return JsonResponse({"status": "ok"})
