from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryRecordViewSet,
    EntranceInfoViewSet,
    MeView,
    OcrImportView,
    AreaListView,
    AreaStatsView,
    AreaTodayPlanView,
    AiConsentView,
)

router = DefaultRouter()
router.register(r"deliveries", DeliveryRecordViewSet, basename="deliveries")
router.register(r"entrances", EntranceInfoViewSet, basename="entrances")

urlpatterns = [
    path("", include(router.urls)),
    path("me/", MeView.as_view(), name="me"),
    path("ocr/import/", OcrImportView.as_view(), name="ocr-import"),
    # エリア関連
    path("areas/list/", AreaListView.as_view(), name="areas-list"),
    path("areas/stats/", AreaStatsView.as_view(), name="areas-stats"),
    path("areas/today_plan/", AreaTodayPlanView.as_view(), name="areas-today-plan"),
    # 同意
    path("consent/", AiConsentView.as_view(), name="ai-consent"),
]
