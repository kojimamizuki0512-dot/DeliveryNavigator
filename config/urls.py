from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Home と healthz は config.views から
from . import views
# ダッシュボード/マップは core 側のまま
from core.views import DashboardView, MapView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API
    path('api/', include('core.urls')),

    # ユーザー向け画面
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('map/', MapView.as_view(), name='map'),

    path('healthz', views.healthz),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
