# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserAiConsent

User = get_user_model()

@receiver(post_save, sender=User)
def create_consent_for_new_user(sender, instance, created, **kwargs):
    if created:
        UserAiConsent.objects.get_or_create(user=instance)
