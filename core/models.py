from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.conf import settings


# --- 1. ユーザー ---
class User(AbstractUser):
    nickname = models.CharField(max_length=50, blank=True, null=True)
    platform = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.username


# --- 2. 配達実績 ---
class DeliveryRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="delivery_records")
    date = models.DateField()
    orders_completed = models.PositiveIntegerField(validators=[MinValueValidator(0)], default=0)
    earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.TimeField(null=True, blank=True)  # その日の開始時刻（任意）
    end_time   = models.TimeField(null=True, blank=True)  # その日の終了時刻（任意）
    # エリア学習で使うタグ（例：[AREA:shibuya-center] を先頭に付与）
    note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("user", "date")
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.date}"


# --- 3. 入口共有 ---
class EntranceInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entrances")
    address = models.CharField(max_length=255)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    photo1 = models.ImageField(upload_to="entrances/", blank=True, null=True)
    photo2 = models.ImageField(upload_to="entrances/", blank=True, null=True)
    photo3 = models.ImageField(upload_to="entrances/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Entrance - {self.address}"


# --- 4. OCRインポート履歴（任意だがあると便利） ---
class OcrImport(models.Model):
    STATUS_CHOICES = (("success", "success"), ("failed", "failed"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ocr_imports")
    image = models.ImageField(upload_to="ocr/")
    raw_text = models.TextField(blank=True, null=True)
    parsed_json = models.JSONField(default=dict, blank=True)
    created_record = models.ForeignKey(
        DeliveryRecord, on_delete=models.SET_NULL, blank=True, null=True, related_name="ocr_sources"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OCR #{self.id} by {self.user.username}"


# --- 5. 集合学習への同意（Opt-in/Opt-out） ---
class UserAiConsent(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_consent")
    # 匿名集計（エリア×時間の期待時給学習）に自分の実績を使ってよいか
    share_aggregated = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} consent: {'ON' if self.share_aggregated else 'OFF'}"
