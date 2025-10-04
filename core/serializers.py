# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DeliveryRecord, EntranceInfo

User = get_user_model()

# --- User public ---
class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "nickname", "platform"]


# --- Delivery ---
class DeliveryRecordSerializer(serializers.ModelSerializer):
    area_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryRecord
        fields = [
            "id", "date", "orders_completed", "earnings", "hours_worked",
            "start_time", "end_time",
            "area_slug", "area_name", "note",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "area_name"]

    def get_area_name(self, obj):
        try:
            from .areas import get_area
            if obj.area_slug:
                a = get_area(obj.area_slug)
                return a["name"]
        except Exception:
            pass
        return None


# --- Entrance ---
class EntranceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceInfo
        fields = ["id", "address", "latitude", "longitude", "note", "photo1", "photo2", "photo3", "created_at"]
        read_only_fields = ["id", "created_at"]


# --- OCR Import input ---
class OcrImportInputSerializer(serializers.Serializer):
    image = serializers.ImageField()
    date = serializers.DateField(required=False, allow_null=True)
    hours_worked = serializers.CharField(required=False, allow_blank=True, allow_null=True)
