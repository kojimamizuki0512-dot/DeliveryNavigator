from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError

from .models import DeliveryRecord


class DeliveryRecordForm(forms.ModelForm):
    class Meta:
        model = DeliveryRecord
        fields = [
            "date",
            "earnings",
            "orders",
            "start_time",
            "end_time",
            "hours",   # モデルに無い場合は削除
            "note",    # モデルに無い場合は削除
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "required": True}),
            "earnings": forms.NumberInput(attrs={
                "inputmode": "decimal", "step": "0.01", "min": "0", "required": True,
                "placeholder": "例) 8250.00"
            }),
            "orders": forms.NumberInput(attrs={
                "inputmode": "numeric", "step": "1", "min": "0", "required": True,
                "placeholder": "例) 12"
            }),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "hours": forms.NumberInput(attrs={  # モデルに無い場合は削除
                "inputmode": "decimal", "step": "0.01", "min": "0",
                "placeholder": "未入力なら自動計算"
            }),
            "note": forms.Textarea(attrs={"rows": 2, "placeholder": "任意メモ"}),  # モデルに無い場合は削除
        }

    # --- 単項目バリデーション ---
    def clean_earnings(self):
        val = self.cleaned_data.get("earnings")
        if val is None:
            raise ValidationError("売上（earnings）は必須です。")
        try:
            dec = Decimal(val)
        except (InvalidOperation, TypeError):
            raise ValidationError("売上は数値で入力してください。")
        if dec < 0:
            raise ValidationError("売上は0以上で入力してください。")

        # 小数2桁までを推奨（3桁以上の入力は丸め）
        return dec.quantize(Decimal("0.01"))

    def clean_orders(self):
        val = self.cleaned_data.get("orders")
        if val is None:
            raise ValidationError("件数（orders）は必須です。")
        try:
            ival = int(val)
        except (ValueError, TypeError):
            raise ValidationError("件数は整数で入力してください。")
        if ival < 0:
            raise ValidationError("件数は0以上で入力してください。")
        return ival

    # --- 複合バリデーション & 自動計算 ---
    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        hours = cleaned.get("hours") if "hours" in self.fields else None

        if start and end:
            # 同日内前提。もし日またぎ運用ならここで補正ルールを入れる
            if end < start:
                raise ValidationError("終了時刻は開始時刻以降にしてください。")

            # 自動計算（hours が無ければ代入）
            delta = (
                datetime.combine(cleaned["date"], end)
                - datetime.combine(cleaned["date"], start)
            )
            auto_hours = round(delta.total_seconds() / 3600, 2)

            if "hours" in self.fields:
                if hours in (None, ""):
                    cleaned["hours"] = Decimal(str(auto_hours))
                else:
                    # 整合チェック（±0.1h までは許容）
                    try:
                        h = Decimal(hours)
                    except InvalidOperation:
                        raise ValidationError("稼働時間（hours）は数値で入力してください。")
                    if abs(h - Decimal(str(auto_hours))) > Decimal("0.10"):
                        raise ValidationError(f"稼働時間が開始/終了と一致しません（自動計算値: {auto_hours}h）。")

        return cleaned
