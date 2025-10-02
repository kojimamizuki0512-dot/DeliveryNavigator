from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from core.views import DashboardView, MapView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),

    # ダッシュボード / 地図
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('map/', MapView.as_view(), name='map'),

    # JWT
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
