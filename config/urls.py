from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Home/healthz は config.views
from . import views
# ダッシュボード/マップ/アップロードは core 側
from core.views import DashboardView, MapView, UploadView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API
    path('api/', include('core.urls')),

    # ユーザー向け画面
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('map/', MapView.as_view(), name='map'),
    path('upload/', UploadView.as_view(), name='upload'),   # ★ 追加

    path('healthz', views.healthz),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
