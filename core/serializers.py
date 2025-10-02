from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DeliveryRecord, EntranceInfo


class DeliveryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = ["id", "date", "orders_completed", "earnings", "hours_worked", "created_at"]
        read_only_fields = ["id", "created_at"]


class EntranceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceInfo
        fields = [
            "id", "address", "latitude", "longitude", "note",
            "photo1", "photo2", "photo3", "created_at"
        ]
        read_only_fields = ["id", "created_at"]


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "nickname", "platform"]
        read_only_fields = ["id", "username", "email"]


# ここは「空文字OK」にして後段で安全に数値化する
class OcrImportInputSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    date = serializers.DateField(required=False, allow_null=True)
    hours_worked = serializers.CharField(required=False, allow_blank=True, allow_null=True)
