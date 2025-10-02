from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryRecordViewSet, EntranceInfoViewSet,
    MeView, OcrImportView
)

router = DefaultRouter()
router.register(r"deliveries", DeliveryRecordViewSet, basename="delivery")
router.register(r"entrances", EntranceInfoViewSet, basename="entrance")

urlpatterns = router.urls + [
    path("me/", MeView.as_view(), name="me"),
    path("ocr/import/", OcrImportView.as_view(), name="ocr-import"),
]
