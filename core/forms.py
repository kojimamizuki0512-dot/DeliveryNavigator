# core/forms.py
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError

from .models import DeliveryRecord
from .areas import area_choices

class DeliveryRecordForm(forms.ModelForm):
    # モデル外の追加フィールド（DBは触らない）
    area_slug = forms.ChoiceField(choices=[("", "（選択しない）")] + area_choices(), required=False, label="エリア")

    class Meta:
        model = DeliveryRecord
        fields = [
            "date", "earnings", "orders_completed", "start_time", "end_time",
            "hours_worked", "note"
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "required": True}),
            "earnings": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01", "min": "0", "required": True}),
            "orders_completed": forms.NumberInput(attrs={"inputmode": "numeric", "step": "1", "min": "0", "required": True}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "hours_worked": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01", "min": "0"}),
            "note": forms.Textarea(attrs={"rows": 2, "placeholder": "メモ（任意）"}),
        }

    def clean_earnings(self):
        val = self.cleaned_data.get("earnings")
        if val is None:
            raise ValidationError("売上は必須です。")
        try:
            dec = Decimal(val)
        except (InvalidOperation, TypeError):
            raise ValidationError("売上は数値で入力してください。")
        if dec < 0:
            raise ValidationError("売上は0以上で入力してください。")
        return dec.quantize(Decimal("0.01"))

    def clean_orders_completed(self):
        val = self.cleaned_data.get("orders_completed")
        if val is None:
            raise ValidationError("件数は必須です。")
        try:
            ival = int(val)
        except (ValueError, TypeError):
            raise ValidationError("件数は整数で入力してください。")
        if ival < 0:
            raise ValidationError("件数は0以上で入力してください。")
        return ival

    def clean(self):
        cleaned = super().clean()
        st, et = cleaned.get("start_time"), cleaned.get("end_time")
        if st and et and et <= st:
            raise ValidationError("終了時刻は開始時刻以降にしてください。")
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        slug = self.cleaned_data.get("area_slug")
        if slug:
            tag = f"[AREA:{slug}] "
            note = getattr(inst, "note", "") or ""
            # 既存タグがあれば置換、無ければ先頭に付与
            if note.startswith("[AREA:"):
                note = re.sub(r"^\[AREA:[^\]]+\]\s*", tag, note)
            else:
                note = tag + note
            inst.note = note
        if commit:
            inst.save()
        return inst
