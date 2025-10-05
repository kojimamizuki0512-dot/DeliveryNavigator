# core/views.py
import io
import re
import csv
import shutil
import datetime
import os
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.core.files.base import ContentFile
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.forms import UserCreationForm
from django import forms

from rest_framework import viewsets, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

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

logger = logging.getLogger(__name__)

# ---------- ユーティリティ ----------

def _ensure_tesseract_path():
    """OSごとの代表パスを探して pytesseract を有効化（settings優先 → 代表的パス → PATH）"""
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
        # Linux
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        # Windows
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.exists(guess):
            pytesseract.pytesseract.tesseract_cmd = guess
            return
    # 見つからない場合は pytesseract 側で例外が発生する


def _ocr_image_to_text(image_bytes: bytes):
    """
    可能なら Google Vision、だめなら Tesseract にフォールバック。
    成功: (text:str, provider:str)  provider は "google-vision" | "tesseract"
    失敗: (None, None)
    """
    # --- 1) Google Vision ---
    try:
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Creds not found: {creds_path}")
            from google.cloud import vision  # 遅延 import
            client = vision.ImageAnnotatorClient()
            gimg = vision.Image(content=image_bytes)
            resp = client.text_detection(image=gimg)
            if getattr(resp, "error", None) and resp.error.message:
                raise RuntimeError(resp.error.message)
            if resp.text_annotations:
                return resp.text_annotations[0].description, "google-vision"
        else:
            logger.debug("GOOGLE_APPLICATION_CREDENTIALS is not set.")
    except Exception as e:
        logger.warning("Vision fallback: %s", e)

    # --- 2) Tesseract ---
    try:
        _ensure_tesseract_path()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        cfg = "--psm 6"
        try:
            return pytesseract.image_to_string(img, lang="jpn+eng", config=cfg), "tesseract"
        except Exception:
            return pytesseract.image_to_string(img, lang="eng", config=cfg), "tesseract"
    except Exception as e:
        logger.error("Tesseract OCR failed: %s", e)

    return None, None


def _parse_numbers(text: str):
    """OCR文字列から ゆるく数値を拾う（無ければ None）"""
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


def _parse_times(text: str):
    """
    OCR文字列から start/end の候補を抜く。
    例: 10:00-14:30 / 10:00 ~ 14:30 / 10時〜14時 / Start: 10:00 End: 14:30
    """
    norm = (
        text.replace("：", ":")
            .replace("〜", "-")
            .replace("~", "-")
            .replace("—", "-")
            .replace("–", "-")
    )

    candidates = []

    # hh:mm
    for hh, mm in re.findall(r"(\d{1,2}):(\d{2})", norm):
        h, m = int(hh), int(mm)
        if 0 <= h < 24 and 0 <= m < 60:
            candidates.append(datetime.time(h, m))

    # 日本語「10時30分」「10時」
    for hh, mm in re.findall(r"(\d{1,2})\s*時\s*(\d{1,2})?\s*分?", norm):
        h = int(hh)
        m = int(mm) if mm else 0
        if 0 <= h < 24 and 0 <= m < 60:
            candidates.append(datetime.time(h, m))

    # 「10 - 14」のように時だけ
    m = re.search(r"\b(\d{1,2})\s*[-–~]\s*(\d{1,2})\b", norm)
    if m:
        h1, h2 = int(m.group(1)), int(m.group(2))
        if 0 <= h1 < 24 and 0 <= h2 < 24:
            if len(candidates) < 1:
                candidates.append(datetime.time(h1, 0))
            if len(candidates) < 2:
                candidates.append(datetime.time(h2, 0))

    start = candidates[0] if len(candidates) >= 1 else None
    end   = candidates[1] if len(candidates) >= 2 else None
    return start, end


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


def _add_hours_to_time(t: datetime.time, hours: float) -> datetime.time:
    """time + hours を 24h で丸めて返す"""
    minutes = int(round(hours * 60))
    total = t.hour * 60 + t.minute + minutes
    total %= (24 * 60)
    return datetime.time(total // 60, total % 60)


def _time_diff_in_hours(start: datetime.time, end: datetime.time) -> float:
    """end - start（時間）。日またぎの場合は24hを加味"""
    s = start.hour * 60 + start.minute
    e = end.hour * 60 + end.minute
    if e < s:
        e += 24 * 60
    return round((e - s) / 60.0, 2)


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

            # 同日内のみ。終了<=開始なら hours_worked で補完
            if eh <= sh:
                dur_from_hours = float(r.hours_worked or 0) or 0.0
                if dur_from_hours <= 0:
                    continue
                eh = min(24.0, sh + dur_from_hours)

            dur = max(0.0, eh - sh)
            if dur <= 0:
                continue

            wd = r.date.weekday()  # 0=Mon
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
        for v, wd, h, hrs in slots[:3]:
            top.append({"label": f"{name[wd]} {h:02d}:00", "hourly": round(v), "hours": round(hrs, 1)})

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
    success_url = reverse_lazy("home")  # 登録後はトップへ

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

        hours_override = s.validated_data.get("hours_worked")
        start_override = s.validated_data.get("start_time")
        end_override   = s.validated_data.get("end_time")
        area_slug      = s.validated_data.get("area_slug")
        area_name      = s.validated_data.get("area_name")

        data = image.read()
        raw_text, provider = _ocr_image_to_text(data)

        if not raw_text or not str(raw_text).strip():
            # 500で落とさず、ユーザーに分かる形で返す
            job = OcrImport(user=request.user, status="failed")
            job.image.save(image.name, ContentFile(data))
            job.message = "OCRバックエンドが利用できないか、テキストを抽出できませんでした。"
            job.save()
            return Response(
                {"detail": job.message, "provider": provider},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed = _parse_numbers(raw_text)
        p_start, p_end = _parse_times(raw_text)

        # 優先順位: フォーム上書き > OCR推定
        start_time = start_override or p_start
        end_time   = end_override or p_end

        if date_override:
            parsed["date"] = date_override

        date = parsed["date"] or datetime.date.today()

        # 時刻と時間の補完ロジック
        hours_val = float(hours_override) if hours_override is not None else parsed["hours"]

        if (start_time is not None) and (end_time is None) and (hours_val is not None):
            end_time = _add_hours_to_time(start_time, float(hours_val))
        elif (end_time is not None) and (start_time is None) and (hours_val is not None):
            start_time = _add_hours_to_time(end_time, -float(hours_val))

        # hours が無ければ、start/end から逆算
        if (hours_val is None) and (start_time is not None) and (end_time is not None):
            hours_val = _time_diff_in_hours(start_time, end_time)

        # DB 用デフォルト
        defaults = {}
        if parsed["orders"] is not None:
            defaults["orders_completed"] = int(parsed["orders"])
        dec = _to_decimal_or_none(parsed["earnings"])
        if dec is not None:
            defaults["earnings"] = dec

        dec = _to_decimal_or_none(hours_val)
        if dec is not None:
            defaults["hours_worked"] = dec

        # 既存の同日レコードをUpsert
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
            dec = _to_decimal_or_none(hours_val)
            if dec is not None:
                rec.hours_worked = dec
                updated_fields.append("hours_worked")

        # 時刻・エリアの反映
        if start_time is not None:
            rec.start_time = start_time
            if "start_time" not in updated_fields:
                updated_fields.append("start_time")
        if end_time is not None:
            rec.end_time = end_time
            if "end_time" not in updated_fields:
                updated_fields.append("end_time")

        if hasattr(rec, "area_slug") and area_slug:
            rec.area_slug = area_slug
            updated_fields.append("area_slug")
        if hasattr(rec, "area_name") and area_name:
            rec.area_name = area_name
            updated_fields.append("area_name")

        if updated_fields:
            rec.save(update_fields=updated_fields)

        job = OcrImport(user=request.user, status="success")
        job.image.save(image.name, ContentFile(data))
        job.raw_text = raw_text
        job.parsed_json = {
            "date": date.isoformat(),
            "orders": parsed["orders"],
            "earnings": parsed["earnings"],
            "hours": hours_val,
            "start_time": None if start_time is None else start_time.isoformat(),
            "end_time": None if end_time is None else end_time.isoformat(),
            "provider": provider,
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


# ---------- Areas（地図用エリア定義の配信） ----------

class AreasListView(LoginRequiredMixin, View):
    """
    GET /api/areas/
    core/areas.py の AREAS を返すだけの最小実装。将来はDB/推論スコアをここに載せる。
    """
    login_url = '/login/'

    def get(self, request):
        try:
            from .areas import AREAS
        except Exception:
            AREAS = []
        return JsonResponse({"areas": AREAS})


class AreasStatsView(APIView):
    """
    GET /api/areas/stats/?hour=15&top=3
    ひとまず公開GETで返すダミー実装（集計ロジックは後で差し替え）。
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            from .areas import AREAS
        except Exception:
            AREAS = []

        # hour, top のパラメータ
        try:
            hour = int(request.GET.get("hour", datetime.datetime.now().hour))
            hour = max(0, min(23, hour))
        except Exception:
            hour = datetime.datetime.now().hour

        try:
            top_n = int(request.GET.get("top", 3))
            top_n = max(1, min(5, top_n))
        except Exception:
            top_n = 3

        # TODO: 実データからのスコアに差し替える
        items = []
        for a in AREAS:
            items.append({
                "id": a.get("id"),
                "name": a.get("name"),
                "center": a.get("center"),
                "score": 0.0,
                "hour": hour,
                "reason": "データ準備中（ダミー）",
            })

        top = items[:top_n]
        return Response({"hour": hour, "top": top, "items": items})
