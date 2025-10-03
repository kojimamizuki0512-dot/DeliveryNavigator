from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.views import HomeView, DashboardView, MapView, healthz

urlpatterns = [
    path('admin/', admin.site.urls),

    # API
    path('api/', include('core.urls')),

    # ユーザー向け画面
    path('', HomeView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('map/', MapView.as_view(), name='map'),

    path('healthz', healthz),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
