# core/serializers.py
from rest_framework import serializers
from .models import DeliveryRecord, EntranceInfo
from django.contrib.auth import get_user_model

class DeliveryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = [
            "id", "date",
            "orders_completed", "earnings", "hours_worked",
            "start_time", "end_time",           # ★ 追加
            "created_at",
        ]

class EntranceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceInfo
        fields = ["id", "address", "note", "lat", "lng", "created_at"]

class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email"]
