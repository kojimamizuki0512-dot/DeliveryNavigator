import io
import re
import csv
import shutil
import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.core.files.base import ContentFile
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from rest_framework import viewsets, permissions, generics
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
    # psm=6 は 1 段落のブロックとして読みやすいモード（表形式でない単純な画面に強い）
    cfg = "--psm 6"
    try:
        return pytesseract.image_to_string(img, lang="jpn+eng", config=cfg)
    except Exception:
        return pytesseract.image_to_string(img, lang="eng", config=cfg)


def _parse_numbers(text: str):
    """
    OCR文字列から ゆるく数値を拾う（無ければ None）
    - 日付: YYYY[-./]MM[-./]DD
    - 件数: 「◯件」/「Orders: 12」/「Deliveries: 12」など
    - 売上: 円/¥/JPY 付きの数値や「Earnings: 5600 JPY」
    - 時間: 「3.5 h」/「3.5時間」/「Hours: 3.5 h」
    """
    # 正規化（全角コロンなど）
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

    # 件数（優先: ラベル → 末尾「件」）
    orders = None
    for pat in [
        r"\bOrders?\s*:\s*(\d+)\b",                  # Orders: 12 / Order: 1
        r"\bDeliveries?\s*:\s*(\d+)\b",               # Deliveries: 12
        r"(?:件数|配達回数|配達数|注文数|オーダー数)\s*:\s*(\d+)",  # 日本語ラベル
        r"(\d+)\s*件",                                 # 12件
    ]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try:
                orders = int(m.group(1))
                break
            except Exception:
                pass

    # 売上（優先: Earningsラベル → 通貨付き数値の最大）
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

    # 稼働時間（優先: Hoursラベル → 単位付き）
    hours = None
    for pat in [
        r"\bHours?\s*:\s*(\d+(?:\.\d+)?)\s*h\b",     # Hours: 3.5 h
        r"(\d+(?:\.\d+)?)\s*(?:h|時間)\b",           # 3.5 h / 3.5時間
    ]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try:
                hours = float(m.group(1))
                break
            except Exception:
                pass

    return {"date": date, "orders": orders, "earnings": earnings, "hours": hours}


# Decimal を安全に作る（None/空/非数値は None を返す）
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
    """
    既存データの『不正な文字列』を安全な値に修復する。
    - earnings: NOT NULL のため '0' に置換
    - hours_worked: NULL 許可のため NULL に置換
    """
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
        w.writerow(["date", "orders_completed", "earnings", "hours_worked", "created_at"])
        for r in qs.order_by("date"):
            w.writerow([
                r.date,
                r.orders_completed,
                str(r.earnings),
                "" if r.hours_worked is None else str(r.hours_worked),
                r.created_at.isoformat(),
            ])
        return resp


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


class DashboardView(LoginRequiredMixin, TemplateView):
    login_url = '/admin/login/'
    template_name = 'dashboard.html'


class MapView(LoginRequiredMixin, TemplateView):
    login_url = '/admin/login/'
    template_name = 'map.html'


class OcrImportView(generics.GenericAPIView):
    """
    POST /api/ocr/import/
      - image: ファイル必須（スクショ）
      - date (任意, YYYY-MM-DD) … 読み取り上書き
      - hours_worked (任意, 数字) … 読み取り上書き（空欄OK）
    戻り値:
      {
        "created": true/false,
        "updated_fields": [...],
        "record": {...},
        "parsed": {...},
        "raw_text": "..."
      }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = OcrImportInputSerializer

    def post(self, request, *args, **kwargs):
        # まず既存DBの不正値を自動修復
        _repair_decimal_columns()

        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)

        image = s.validated_data["image"]
        date_override = s.validated_data.get("date")

        # hours_worked は空でも来るので安全に数値化
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

        # 新規作成時の初期値（Noneは保存しない）
        defaults = {}
        if parsed["orders"] is not None:
            defaults["orders_completed"] = int(parsed["orders"])
        dec = _to_decimal_or_none(parsed["earnings"])
        if dec is not None:
            defaults["earnings"] = dec
        dec = _to_decimal_or_none(parsed["hours"])
        if dec is not None:
            defaults["hours_worked"] = dec

        # 既存レコードの安全取得（Decimal列を読み込まない）
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
            rec.earnings = defaults.get("earnings", Decimal("0.00"))  # NOT NULL想定
            rec.hours_worked = defaults.get("hours_worked", None)
            rec.save()
            created = True

        # 既存なら「読めた項目だけ」更新（Decimalは必ず quantize 済）
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

        # OCRログ
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

        # 念のため、直後のシリアライズでも落ちないよう rec を最新で取得
        rec = DeliveryRecord.objects.get(pk=rec.pk)

        return Response({
            "created": created,
            "updated_fields": updated_fields,
            "record": DeliveryRecordSerializer(rec).data,
            "parsed": job.parsed_json,
            "raw_text": raw_text,
        }, status=201)

# ...既存の import の下あたりに追加
from django.http import JsonResponse

def healthz(request):
    return JsonResponse({"status": "ok"})