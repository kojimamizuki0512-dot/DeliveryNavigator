# core/views.py
import io
import re
import csv
import shutil
import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.core.files.base import ContentFile
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.forms import UserCreationForm
from django import forms

from rest_framework import viewsets, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from django.db.models import Q, Sum
from django.db import connection  # 既存データの修復に使用

from PIL import Image
import pytesseract

from .models import DeliveryRecord, EntranceInfo, OcrImport
from .serializers import (
    DeliveryRecordSerializer,
    EntranceInfoSerializer,
    UserPublicSerializer,
    OcrImportInputSerializer,
)

# ---------- ユーティリティ ----------

def _ensure_tesseract_path():
    """Windowsで tesseract.exe の場所を設定（settings優先 → 代表的パス → PATH）"""
    import os
    if shutil.which("tesseract"):
        return
    try:
        from django.conf import settings
        cmd = getattr(settings, "TESSERACT_CMD", None)
        if cmd and os.path.exists(cmd):
            pytesseract.pytesseract.tesseract_cmd = cmd
            return
    except Exception:
        pass
    for guess in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.exists(guess):
            pytesseract.pytesseract.tesseract_cmd = guess
            return
    # 見つからない場合は pytesseract 側で例外が発生


def _ocr_image_to_text(image_bytes: bytes) -> str:
    _ensure_tesseract_path()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    cfg = "--psm 6"
    try:
        return pytesseract.image_to_string(img, lang="jpn+eng", config=cfg)
    except Exception:
        return pytesseract.image_to_string(img, lang="eng", config=cfg)


def _parse_numbers(text: str):
    """
    OCR文字列から ゆるく数値を拾う（無ければ None）
    """
    norm = text.replace("：", ":").replace("　", " ")

    # 日付
    date = None
    m = re.search(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", norm)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            date = datetime.date(y, mo, d)
        except ValueError:
            date = None

    # 件数
    orders = None
    for pat in [
        r"\bOrders?\s*:\s*(\d+)\b",
        r"\bDeliveries?\s*:\s*(\d+)\b",
        r"(?:件数|配達回数|配達数|注文数|オーダー数)\s*:\s*(\d+)",
        r"(\d+)\s*件",
    ]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try:
                orders = int(m.group(1))
                break
            except Exception:
                pass

    # 売上
    earnings = None
    m = re.search(r"\bEarnings?\s*:\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", norm, re.IGNORECASE)
    if m:
        try:
            earnings = int(m.group(1).replace(",", ""))
        except Exception:
            earnings = None
    if earnings is None:
        nums = re.findall(r"[¥\u00A5]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s*(?:円|JPY|¥)?", norm)
        if nums:
            try:
                candidates = [int(n.replace(",", "")) for n in nums]
                earnings = max(candidates)
            except Exception:
                pass

    # 稼働時間
    hours = None
    for pat in [
        r"\bHours?\s*:\s*(\d+(?:\.\d+)?)\s*h\b",
        r"(\d+(?:\.\d+)?)\s*(?:h|時間)\b",
    ]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try:
                hours = float(m.group(1))
                break
            except Exception:
                pass

    return {"date": date, "orders": orders, "earnings": earnings, "hours": hours}


# Decimal を安全に作る
Q2 = Decimal("0.01")
def _to_decimal_or_none(val):
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    try:
        d = Decimal(str(val))
        if not d.is_finite():
            return None
        return d.quantize(Q2, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _repair_decimal_columns():
    """既存データの不正値を安全に修復する。"""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE core_deliveryrecord "
                "SET earnings='0' "
                "WHERE earnings IS NOT NULL AND (trim(earnings)='' OR lower(earnings) IN ('nan','inf','-inf'))"
            )
            cur.execute(
                "UPDATE core_deliveryrecord "
                "SET hours_worked=NULL "
                "WHERE hours_worked IS NOT NULL AND (trim(hours_worked)='' OR lower(hours_worked) IN ('nan','inf','-inf'))"
            )
    except Exception:
        pass


# ---------- API ----------

class DeliveryRecordViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DeliveryRecord.objects.filter(user=self.request.user).order_by("-date")
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start:
            d = parse_date(start)
            if d:
                qs = qs.filter(date__gte=d)
        if end:
            d = parse_date(end)
            if d:
                qs = qs.filter(date__lte=d)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_orders=Sum("orders_completed"),
            total_earnings=Sum("earnings"),
            total_hours=Sum("hours_worked"),
        )
        total_orders = int(agg["total_orders"] or 0)
        total_earnings = float(agg["total_earnings"] or 0)
        total_hours = float(agg["total_hours"] or 0)
        hourly = total_hours and (total_earnings / total_hours) or None
        return Response({
            "count": qs.count(),
            "total_orders": total_orders,
            "total_earnings": total_earnings,
            "total_hours": total_hours,
            "hourly_rate": hourly,
        })

    @action(detail=False, methods=["get"])
    def export(self, request):
        qs = self.get_queryset()
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp['Content-Disposition'] = 'attachment; filename="deliveries.csv"'
        w = csv.writer(resp)
        w.writerow(["date", "orders_completed", "earnings", "hours_worked", "start_time", "end_time", "created_at"])
        for r in qs.order_by("date"):
            w.writerow([
                r.date,
                r.orders_completed,
                str(r.earnings),
                "" if r.hours_worked is None else str(r.hours_worked),
                "" if r.start_time is None else r.start_time.isoformat(),
                "" if r.end_time   is None else r.end_time.isoformat(),
                r.created_at.isoformat(),
            ])
        return resp

    @action(detail=False, methods=["get"])
    def heatmap(self, request):
        """
        GET /api/deliveries/heatmap?start=YYYY-MM-DD&end=YYYY-MM-DD
        返却: 7x24 の行列（weekday=0..6/月..日, hour=0..23）
          values: その時間帯の平均時給（円/h）
          counts: 積算した有効時間（h）サンプル量
          top_slots: 推奨スロット（上位3件）
        """
        from math import floor, ceil

        qs = self.get_queryset().only(
            "date", "earnings", "hours_worked", "start_time", "end_time"
        )

        # 集計バッファ
        sum_earn = [[0.0 for _ in range(24)] for _ in range(7)]
        sum_hours = [[0.0 for _ in range(24)] for _ in range(7)]

        for r in qs:
            if not r.start_time or not r.end_time or not r.earnings:
                # 時刻が無いデータはヒートマップには使わない（誤学習防止）
                continue

            sh = r.start_time.hour + r.start_time.minute / 60.0
            eh = r.end_time.hour + r.end_time.minute / 60.0

            # 同日内のみ（えいっで丸め）。終了<=開始なら hours_worked で補完
            if eh <= sh:
                dur = float(r.hours_worked or 0) or 0.0
                if dur <= 0:
                    continue
                eh = min(24.0, sh + dur)

            dur = max(0.0, eh - sh)
            if dur <= 0:
                continue

            wd = r.date.weekday()  # 0=Mon
            # 時給を時間配分して加算
            earn = float(r.earnings)
            for h in range(max(0, floor(sh)), min(24, ceil(eh))):
                # その時間枠にどれくらい被っているか（0..1）
                left = max(sh, h)
                right = min(eh, h + 1)
                portion = max(0.0, right - left)
                if portion > 0:
                    sum_earn[wd][h] += earn * (portion / dur)
                    sum_hours[wd][h] += portion

        # 平均時給 matrix を作成
        values = []
        vmax = 0.0
        for wd in range(7):
            row = []
            for h in range(24):
                hrs = sum_hours[wd][h]
                val = (sum_earn[wd][h] / hrs) if hrs > 0 else 0.0
                row.append(round(val, 2))
                vmax = max(vmax, val)
            values.append(row)

        # 推奨スロット（上位3件、サンプル1時間以上）
        slots = []
        for wd in range(7):
            for h in range(24):
                if sum_hours[wd][h] >= 1.0:  # 1時間以上のサンプル
                    slots.append((values[wd][h], wd, h, sum_hours[wd][h]))
        slots.sort(reverse=True, key=lambda x: x[0])
        name = ["月","火","水","木","金","土","日"]
        top = []
        for i, (v, wd, h, hrs) in enumerate(slots[:3]):
            top.append({"label": f"{name[wd]} {h:02d}:00", "hourly": round(v), "hours": round(hrs,1)})

        return Response({
            "values": values,
            "counts": sum_hours,
            "vmax": round(vmax),
            "top_slots": top,
        })
    
    


class EntranceInfoViewSet(viewsets.ModelViewSet):
    serializer_class = EntranceInfoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = EntranceInfo.objects.filter(user=self.request.user).order_by("-created_at")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(address__icontains=q) | Q(note__icontains=q))
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserPublicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ---------- 画面（ユーザー向け） ----------

class DashboardView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    template_name = 'dashboard.html'


class MapView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    template_name = 'map.html'


class UploadView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'
    template_name = 'upload.html'


class RecordsView(LoginRequiredMixin, TemplateView):
    """実績一覧/編集（フロントはAPI呼び出し）"""
    login_url = '/login/'
    template_name = 'records.html'


# ---------- サインアップ（UI） ----------

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")  # password1/password2 は UserCreationForm が持つ


class SignUpView(FormView):
    template_name = "signup.html"
    form_class = SignUpForm
    # 登録後はトップへ
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = form.save()
        auth_login(self.request, user)  # 登録後そのままログイン
        return super().form_valid(form)


# ---------- OCR 取り込み ----------

class OcrImportView(generics.GenericAPIView):
    """
    POST /api/ocr/import/
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = OcrImportInputSerializer

    def post(self, request, *args, **kwargs):
        _repair_decimal_columns()

        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)

        image = s.validated_data["image"]
        date_override = s.validated_data.get("date")

        hours_raw = s.validated_data.get("hours_worked")
        hours_override = None
        if hours_raw is not None:
            try:
                if isinstance(hours_raw, str) and hours_raw.strip() == "":
                    hours_override = None
                else:
                    hours_override = float(str(hours_raw).strip())
            except Exception:
                hours_override = None

        data = image.read()
        raw_text = _ocr_image_to_text(data)
        parsed = _parse_numbers(raw_text)

        if date_override:
            parsed["date"] = date_override
        if hours_override is not None:
            parsed["hours"] = hours_override

        date = parsed["date"] or datetime.date.today()

        defaults = {}
        if parsed["orders"] is not None:
            defaults["orders_completed"] = int(parsed["orders"])
        dec = _to_decimal_or_none(parsed["earnings"])
        if dec is not None:
            defaults["earnings"] = dec
        dec = _to_decimal_or_none(parsed["hours"])
        if dec is not None:
            defaults["hours_worked"] = dec

        existing_id = (
            DeliveryRecord.objects
            .filter(user=request.user, date=date)
            .only("id")
            .values_list("id", flat=True)
            .first()
        )

        if existing_id:
            rec = DeliveryRecord.objects.only("id").get(pk=existing_id)
            created = False
        else:
            rec = DeliveryRecord(user=request.user, date=date)
            rec.orders_completed = defaults.get("orders_completed", 0)
            rec.earnings = defaults.get("earnings", Decimal("0.00"))
            rec.hours_worked = defaults.get("hours_worked", None)
            rec.save()
            created = True

        updated_fields = []
        if not created:
            if parsed["orders"] is not None:
                rec.orders_completed = int(parsed["orders"])
                updated_fields.append("orders_completed")
            dec = _to_decimal_or_none(parsed["earnings"])
            if dec is not None:
                rec.earnings = dec
                updated_fields.append("earnings")
            dec = _to_decimal_or_none(parsed["hours"])
            if dec is not None:
                rec.hours_worked = dec
                updated_fields.append("hours_worked")
            if updated_fields:
                rec.save(update_fields=updated_fields)

        job = OcrImport(user=request.user, status="success")
        job.image.save(image.name, ContentFile(data))
        job.raw_text = raw_text
        job.parsed_json = {
            "date": date.isoformat(),
            "orders": parsed["orders"],
            "earnings": parsed["earnings"],
            "hours": parsed["hours"],
        }
        job.created_record = rec
        job.save()

        rec = DeliveryRecord.objects.get(pk=rec.pk)

        return Response({
            "created": created,
            "updated_fields": updated_fields,
            "record": DeliveryRecordSerializer(rec).data,
            "parsed": job.parsed_json,
            "raw_text": raw_text,
        }, status=status.HTTP_201_CREATED)
