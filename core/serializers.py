# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import DeliveryRecord, EntranceInfo


class DeliveryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = [
            "id",
            "date",
            "orders_completed",
            "earnings",
            "hours_worked",
            "start_time",   # 追加済みの時刻フィールド
            "end_time",     # 追加済みの時刻フィールド
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class EntranceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceInfo
        fields = ["id", "address", "note", "lat", "lng", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email"]


# ===== OCR 取込用（/api/ocr/import/ の入力）=====
# hours_worked は空文字も来るので CharField にしておき、view 側で安全に数値化します。
class OcrImportInputSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    date = serializers.DateField(required=False, allow_null=True)
    hours_worked = serializers.CharField(required=False, allow_blank=True, allow_null=True)
