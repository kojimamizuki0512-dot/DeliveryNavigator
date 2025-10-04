# core/serializers_consent.py
from rest_framework import serializers
from .models import UserAiConsent

class AiConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAiConsent
        fields = ["share_aggregated", "updated_at"]
        read_only_fields = ["updated_at"]
