# core/views.py
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
from django.views.generic import TemplateView, FormView
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
from django.utils import timezone

from PIL import Image
import pytesseract

from .models import DeliveryRecord, EntranceInfo, OcrImport
from .serializers import (
    DeliveryRecordSerializer,
    EntranceInfoSerializer,
    UserPublicSerializer,
    OcrImportInputSerializer,
)

# ===== エリア関係（新規） =====
from .areas import AREAS, AREAS_BY_SLUG, get_area, distance_km_between

# ---------- ユーティリティ ----------

def _ensure_tesseract_path():
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

def _ocr_image_to_text(image_bytes: bytes) -> str:
    _ensure_tesseract_path()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    cfg = "--psm 6"
    try:
        return pytesseract.image_to_string(img, lang="jpn+eng", config=cfg)
    except Exception:
        return pytesseract.image_to_string(img, lang="eng", config=cfg)

def _parse_numbers(text: str):
    norm = text.replace("：", ":").replace("　", " ")
    date = None
    m = re.search(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", norm)
    if m:
        y, mo, d = map(int, m.groups())
        try: date = datetime.date(y, mo, d)
        except ValueError: date = None

    orders = None
    for pat in [r"\bOrders?\s*:\s*(\d+)\b", r"\bDeliveries?\s*:\s*(\d+)\b",
                r"(?:件数|配達回数|配達数|注文数|オーダー数)\s*:\s*(\d+)", r"(\d+)\s*件"]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try: orders = int(m.group(1)); break
            except Exception: pass

    earnings = None
    m = re.search(r"\bEarnings?\s*:\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", norm, re.IGNORECASE)
    if m:
        try: earnings = int(m.group(1).replace(",", ""))
        except Exception: earnings = None
    if earnings is None:
        nums = re.findall(r"[¥\u00A5]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s*(?:円|JPY|¥)?", norm)
        if nums:
            try: earnings = max(int(n.replace(",", "")) for n in nums)
            except Exception: pass

    hours = None
    for pat in [r"\bHours?\s*:\s*(\d+(?:\.\d+)?)\s*h\b", r"(\d+(?:\.\d+)?)\s*(?:h|時間)\b"]:
        m = re.search(pat, norm, re.IGNORECASE)
        if m:
            try: hours = float(m.group(1)); break
            except Exception: pass

    return {"date": date, "orders": orders, "earnings": earnings, "hours": hours}

Q2 = Decimal("0.01")
def _to_decimal_or_none(val):
    if val is None: return None
    if isinstance(val, str) and val.strip() == "": return None
    try:
        d = Decimal(str(val))
        if not d.is_finite(): return None
        return d.quantize(Q2, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None

def _repair_decimal_columns():
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE core_deliveryrecord
                   SET earnings = '0'
                 WHERE earnings IS NOT NULL
                   AND (trim(earnings::text) = '' OR lower(earnings::text) IN ('nan','inf','-inf'))
                """
            )
            cur.execute(
                """
                UPDATE core_deliveryrecord
                   SET hours_worked = NULL
                 WHERE hours_worked IS NOT NULL
                   AND (trim(hours_worked::text) = '' OR lower(hours_worked::text) IN ('nan','inf','-inf'))
                """
            )
    except Exception:
        pass

# ======== 既存 API ========

class DeliveryRecordViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DeliveryRecord.objects.filter(user=self.request.user).order_by("-date")
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start:
            d = parse_date(start)
            if d: qs = qs.filter(date__gte=d)
        if end:
            d = parse_date(end)
            if d: qs = qs.filter(date__lte=d)
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
        hourly = total_earnings / total_hours if total_hours > 0 else None
        return Response({
            "count": qs.count(),
            "total_orders": total_orders,
            "total_earnings": round(total_earnings, 2),
            "total_hours": round(total_hours, 2),
            "hourly_rate": round(hourly, 2) if hourly is not None else None,
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
        from math import floor, ceil
        qs = self.get_queryset().only("date","earnings","hours_worked","start_time","end_time")
        sum_earn = [[0.0 for _ in range(24)] for _ in range(7)]
        sum_hours = [[0.0 for _ in range(24)] for _ in range(7)]
        for r in qs:
            if (r.start_time is None) or (r.end_time is None) or (r.earnings is None):
                continue
            sh = r.start_time.hour + r.start_time.minute/60.0
            eh = r.end_time.hour + r.end_time.minute/60.0
            if eh <= sh:
                dur = float(r.hours_worked or 0) or 0.0
                if dur <= 0: continue
                eh = min(24.0, sh + dur)
            dur = max(0.0, eh - sh)
            if dur <= 0: continue
            wd = r.date.weekday()
            earn = float(r.earnings)
            for h in range(max(0, floor(sh)), min(24, ceil(eh))):
                left = max(sh, h); right = min(eh, h+1); portion = max(0.0, right-left)
                if portion > 0:
                    sum_earn[wd][h] += earn * (portion/dur)
                    sum_hours[wd][h] += portion
        values, vmax = [], 0.0
        for wd in range(7):
            row = []
            for h in range(24):
                hrs = sum_hours[wd][h]
                val = (sum_earn[wd][h]/hrs) if hrs>0 else 0.0
                row.append(round(val,2)); vmax = max(vmax, val)
            values.append(row)
        slots, name = [], ["月","火","水","木","金","土","日"]
        for wd in range(7):
            for h in range(24):
                if sum_hours[wd][h] >= 1.0:
                    slots.append((values[wd][h], wd, h, sum_hours[wd][h]))
        slots.sort(reverse=True, key=lambda x: x[0])
        top = []
        for v, wd, h, hrs in slots[:3]:
            top.append({"label": f"{name[wd]} {h:02d}:00", "hourly": round(v), "hours": round(hrs,1)})
        return Response({"values": values, "counts": sum_hours, "vmax": round(vmax), "top_slots": top})

class EntranceInfoViewSet(viewsets.ModelViewSet):
    serializer_class = EntranceInfoSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        qs = EntranceInfo.objects.filter(user=self.request.user).order_by("-created_at")
        q = self.request.query_params.get("q")
        if q: qs = qs.filter(Q(address__icontains=q) | Q(note__icontains=q))
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
    login_url = '/login/'; template_name = 'dashboard.html'
class MapView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'; template_name = 'map.html'
class UploadView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'; template_name = 'upload.html'
class RecordsView(LoginRequiredMixin, TemplateView):
    login_url = '/login/'; template_name = 'records.html'
class HomeView(TemplateView):
    template_name = 'home.html'

# ---------- サインアップUI ----------
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

class SignUpView(FormView):
    template_name = "signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("home")
    def form_valid(self, form):
        user = form.save(); auth_login(self.request, user)
        return super().form_valid(form)

# ---------- OCR 取り込み ----------
class OcrImportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = OcrImportInputSerializer

    def post(self, request, *args, **kwargs):
        _repair_decimal_columns()
        s = self.get_serializer(data=request.data); s.is_valid(raise_exception=True)
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
        if date_override: parsed["date"] = date_override
        if hours_override is not None: parsed["hours"] = hours_override
        date = parsed["date"] or datetime.date.today()
        defaults = {}
        if parsed["orders"] is not None:
            defaults["orders_completed"] = int(parsed["orders"])
        dec = _to_decimal_or_none(parsed["earnings"])
        if dec is not None: defaults["earnings"] = dec
        dec = _to_decimal_or_none(parsed["hours"])
        if dec is not None: defaults["hours_worked"] = dec
        existing_id = (
            DeliveryRecord.objects
            .filter(user=request.user, date=date)
            .only("id").values_list("id", flat=True).first()
        )
        if existing_id:
            rec = DeliveryRecord.objects.only("id").get(pk=existing_id)
            created = False
        else:
            rec = DeliveryRecord(user=request.user, date=date)
            rec.orders_completed = defaults.get("orders_completed", 0)
            rec.earnings = defaults.get("earnings", Decimal("0.00"))
            rec.hours_worked = defaults.get("hours_worked", None)
            rec.save(); created = True
        updated_fields = []
        if not created:
            if parsed["orders"] is not None:
                rec.orders_completed = int(parsed["orders"]); updated_fields.append("orders_completed")
            dec = _to_decimal_or_none(parsed["earnings"])
            if dec is not None:
                rec.earnings = dec; updated_fields.append("earnings")
            dec = _to_decimal_or_none(parsed["hours"])
            if dec is not None:
                rec.hours_worked = dec; updated_fields.append("hours_worked")
            if updated_fields: rec.save(update_fields=updated_fields)
        job = OcrImport(user=request.user, status="success")
        job.image.save(image.name or "upload.png", ContentFile(data))
        job.raw_text = raw_text
        job.parsed_json = {
            "date": date.isoformat(),
            "orders": parsed["orders"],
            "earnings": parsed["earnings"],
            "hours": parsed["hours"],
        }
        job.created_record = rec; job.save()
        rec = DeliveryRecord.objects.get(pk=rec.pk)
        return Response({
            "created": created,
            "updated_fields": updated_fields,
            "record": DeliveryRecordSerializer(rec).data,
            "parsed": job.parsed_json,
            "raw_text": raw_text,
        }, status=status.HTTP_201_CREATED)

# ======== ここから新規API：エリア統計と今日のルート ========

_AREA_TAG_RE = re.compile(r"\[AREA:([a-z0-9\-]+)\]")

def _extract_area_slug(note: str) -> str | None:
    if not note: return None
    m = _AREA_TAG_RE.search(note)
    return m.group(1) if m else None

def _hourly_stats_for(dow: int, hour: int, lookback_days: int = 28):
    """
    指定 (dow,hour) における各エリアの期待時給を計算。
    前提: DeliveryRecord.note の先頭に [AREA:slug] が付与されていること。
    start_time/end_time があるレコードのみ時間帯配分に使用。
    返り値: dict {slug: {"hourly": float, "samples_h": float}}
    """
    since = (timezone.now() - datetime.timedelta(days=lookback_days)).date()
    qs = DeliveryRecord.objects.filter(date__gte=since)

    # 集計バッファ
    sum_earn = {}   # (slug) -> 円
    sum_hours = {}  # (slug) -> 時間
    total_earn = 0.0
    total_hours = 0.0

    for r in qs.only("date","earnings","hours_worked","start_time","end_time","note"):
        slug = _extract_area_slug(getattr(r, "note", ""))
        if not slug or slug not in AREAS_BY_SLUG: 
            continue
        if (r.start_time is None) or (r.end_time is None) or (r.earnings is None):
            continue  # 時間帯配分ができないためスキップ

        sh = r.start_time.hour + r.start_time.minute/60.0
        eh = r.end_time.hour + r.end_time.minute/60.0
        if eh <= sh:
            dur = float(r.hours_worked or 0) or 0.0
            if dur <= 0: 
                continue
            eh = min(24.0, sh + dur)
        dur = max(0.0, eh - sh)
        if dur <= 0: 
            continue

        # このレコードの各時間枠へ按分
        from math import floor, ceil
        for h in range(max(0, floor(sh)), min(24, ceil(eh))):
            # dow/hour マッチのみ採用
            if r.date.weekday() != dow or h != hour:
                continue
            left = max(sh, h); right = min(eh, h+1); portion = max(0.0, right-left)
            if portion <= 0: 
                continue
            earn_add = float(r.earnings) * (portion/dur)
            hours_add = portion
            sum_earn[slug] = sum_earn.get(slug, 0.0) + earn_add
            sum_hours[slug] = sum_hours.get(slug, 0.0) + hours_add
            total_earn += earn_add
            total_hours += hours_add

    # 事前分布（全体平均）による縮約
    prior = (total_earn/total_hours) if total_hours > 0 else 0.0
    tau = 2.0  # 擬似サンプル時間（h）

    out = {}
    for slug in AREAS_BY_SLUG.keys():
        hrs = sum_hours.get(slug, 0.0)
        earn = sum_earn.get(slug, 0.0)
        if hrs <= 0:
            hourly = prior
            samples = 0.0
        else:
            hourly = (earn + prior*tau) / (hrs + tau)
            samples = hrs
        out[slug] = {"hourly": round(hourly, 0), "samples_h": round(samples, 1)}
    return out

class AreaListView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        return Response({"areas": AREAS})

class AreaStatsView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        now = timezone.now()
        dow = int(request.GET.get("dow", now.weekday()))
        hour = int(request.GET.get("hour", now.hour))
        stats = _hourly_stats_for(dow, hour)
        rows = []
        for slug, s in stats.items():
            area = get_area(slug)
            rows.append({
                "slug": slug, "name": area["name"], "lat": area["lat"], "lng": area["lng"],
                "hourly": s["hourly"], "samples_h": s["samples_h"]
            })
        rows.sort(key=lambda x: (-x["hourly"], -x["samples_h"]))
        return Response({"dow": dow, "hour": hour, "ranking": rows})

class AreaTodayPlanView(APIView):
    """
    GET /api/areas/today_plan?start=14:00&hours=4
    返却: ブロック化された“今日のAIルート”
    """
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        now = timezone.localtime()
        # 入力
        start_str = request.GET.get("start")
        if start_str:
            hh, mm = map(int, start_str.split(":"))
            start_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if start_dt < now:
                start_dt += datetime.timedelta(days=1) if (hh < now.hour or (hh==now.hour and mm<=now.minute)) else datetime.timedelta()
        else:
            # 直近の15分丸め
            m = (now.minute + 14)//15*15
            start_dt = now.replace(minute=0 if m==60 else m, second=0, microsecond=0)
            if m==60: start_dt += datetime.timedelta(hours=1)
        horizon = int(request.GET.get("hours", "4"))
        beta_per_km = float(request.GET.get("beta", "120"))  # kmあたり時給からの減点（円/h）

        slots = []
        cur_area = None
        t = start_dt
        for i in range(horizon):
            dow, hour = t.weekday(), t.hour
            stats = _hourly_stats_for(dow, hour)
            # 候補 scoring
            best = None
            for slug, s in stats.items():
                score = s["hourly"]
                if cur_area and slug != cur_area:
                    score -= distance_km_between(cur_area, slug) * beta_per_km
                cand = (score, slug, s)
                if (best is None) or (cand[0] > best[0]): best = cand
            if best is None:
                break
            _, chosen_slug, s = best
            slots.append({"at": t.strftime("%H:%M"), "slug": chosen_slug, "hourly": int(s["hourly"]),
                          "samples_h": s["samples_h"]})
            cur_area = chosen_slug
            t += datetime.timedelta(hours=1)

        # 連続同一エリアをまとめる
        blocks = []
        if slots:
            cur = {"start": slots[0]["at"], "end": None, "slug": slots[0]["slug"],
                   "hourlies": [], "samples": 0.0}
            for i, sl in enumerate(slots):
                if sl["slug"] != cur["slug"]:
                    cur["end"] = (datetime.datetime.strptime(slots[i-1]["at"], "%H:%M") 
                                  + datetime.timedelta(hours=1)).strftime("%H:%M")
                    blocks.append(cur)
                    cur = {"start": sl["at"], "end": None, "slug": sl["slug"], "hourlies": [], "samples": 0.0}
                cur["hourlies"].append(sl["hourly"])
                cur["samples"] += float(sl["samples_h"] or 0.0)
            # last block end
            cur["end"] = (datetime.datetime.strptime(slots[-1]["at"], "%H:%M") 
                          + datetime.timedelta(hours=1)).strftime("%H:%M")
            blocks.append(cur)

        # 整形
        out = []
        for b in blocks:
            area = get_area(b["slug"])
            out.append({
                "time": f"{b['start']} - {b['end']}",
                "slug": b["slug"], "name": area["name"], "lat": area["lat"], "lng": area["lng"],
                "expected_hourly": int(sum(b["hourlies"])/len(b["hourlies"])) if b["hourlies"] else 0,
                "samples_h": round(b["samples"], 1)
            })

        return Response({"generated_at": timezone.localtime().isoformat(), "blocks": out})
