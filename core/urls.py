# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryRecordViewSet,
    EntranceInfoViewSet,
    MeView,
    OcrImportView,
)

router = DefaultRouter()
router.register(r"deliveries", DeliveryRecordViewSet, basename="deliveries")
router.register(r"entrances", EntranceInfoViewSet, basename="entrances")

urlpatterns = [
    path("", include(router.urls)),
    path("me/", MeView.as_view(), name="me"),
    path("ocr/import/", OcrImportView.as_view(), name="ocr-import"),
]
