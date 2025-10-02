from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, DeliveryRecord, EntranceInfo, OcrImport


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "nickname", "platform", "is_staff", "is_superuser")


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "orders_completed", "earnings", "hours_worked", "created_at")
    list_filter = ("date", "user")


@admin.register(EntranceInfo)
class EntranceInfoAdmin(admin.ModelAdmin):
    list_display = ("user", "address", "created_at")
    search_fields = ("address", "note")


@admin.register(OcrImport)
class OcrImportAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_record", "created_at")
    readonly_fields = ("raw_text", "parsed_json")
    search_fields = ("raw_text",)
