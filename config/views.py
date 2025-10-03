# config/views.py
from django.http import JsonResponse
from django.views.generic import TemplateView
# DBチェック版にしたい場合は下記を使う: from django.db import connections

class HomeView(TemplateView):
    """トップページ"""
    template_name = "home.html"

def healthz(request):
    # 軽量版。必要になったらDB疎通チェックに差し替え可
    # with connections["default"].cursor() as cur: cur.execute("SELECT 1;")
    return JsonResponse({"status": "ok"})
