# config/urls.py（全文）

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import views
from core.views import DashboardView, MapView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API
    path('api/', include('core.urls')),

    # 画面
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('map/', MapView.as_view(), name='map'),

    # ルートに来たらダッシュボードへ
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),

    path('healthz/', views.healthz),
]

# メディア（OCRアップロード画像など）
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
