import json
import math
import re
import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from core.models import DeliveryRecord, UserAiConsent
from core.areas import AREAS, AREAS_BY_SLUG

# 学習
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from lightgbm import LGBMRegressor

# ONNX 変換
import skl2onnx
from skl2onnx.common.data_types import FloatTensorType
import onnx


AREA_TAG_RE = re.compile(r"\[AREA:([a-z0-9\-]+)\]")


def extract_area_slug(note: str) -> str | None:
    if not note:
        return None
    m = AREA_TAG_RE.search(note)
    return m.group(1) if m else None


def iter_hourly_samples(qs):
    """
    DeliveryRecord から 1時間粒度の学習サンプルを生成。
    1レコードを「跨いだ各時間枠」に比例配分し、時給(円/h)を目的変数として返す。
    戻り値: dict のジェネレータ
    """
    from math import floor, ceil

    for r in qs.only("date", "earnings", "hours_worked", "start_time", "end_time", "note"):
        if (r.start_time is None) or (r.end_time is None) or (r.earnings is None):
            continue

        slug = extract_area_slug(getattr(r, "note", ""))
        if not slug or (slug not in AREAS_BY_SLUG):
            continue

        sh = r.start_time.hour + r.start_time.minute / 60.0
        eh = r.end_time.hour + r.end_time.minute / 60.0
        if eh <= sh:
            dur = float(r.hours_worked or 0) or 0.0
            if dur <= 0:
                continue
            eh = min(24.0, sh + dur)

        dur = max(0.0, eh - sh)
        if dur <= 0:
            continue

        # そのレコードの平均時給（全時間帯で一定とみなす）
        earn = float(r.earnings)
        hourly_rate = (earn / dur) if dur > 0 else 0.0
        if hourly_rate <= 0:
            continue

        for h in range(max(0, floor(sh)), min(24, ceil(eh))):
            left = max(sh, h)
            right = min(eh, h + 1)
            portion = max(0.0, right - left)
            if portion <= 0:
                continue

            yield {
                "date": r.date,
                "dow": r.date.weekday(),     # 0=Mon
                "hour": h,                   # 0..23
                "area_slug": slug,
                "y_hourly": hourly_rate,     # 目的変数（時給）
                "portion": portion           # この時間枠への寄与（重み）
            }


class Command(BaseCommand):
    help = "Train LightGBM model from DeliveryRecord and export ONNX (core/ml/model_lgbm.onnx)."

    def add_arguments(self, parser):
        parser.add_argument("--lookback_days", type=int, default=90, help="学習に使う過去日数（デフォ90日）")
        parser.add_argument("--min_samples", type=int, default=200, help="最低サンプル数（これ未満なら学習スキップ）")
        parser.add_argument("--test_size", type=float, default=0.2, help="検証データの割合")
        parser.add_argument("--seed", type=int, default=42, help="乱数シード")

    def handle(self, *args, **opts):
        lookback_days = opts["lookback_days"]
        min_samples = opts["min_samples"]
        test_size = opts["test_size"]
        seed = opts["seed"]

        since = (timezone.now() - datetime.timedelta(days=lookback_days)).date()
        self.stdout.write(self.style.NOTICE(f"[train_lgbm] since={since} ..."))

        # 同意ONのユーザーのみ
        opted_ids = set(UserAiConsent.objects.filter(share_aggregated=True).values_list("user_id", flat=True))
        if not opted_ids:
            self.stdout.write(self.style.WARNING("同意ONユーザーがいません。学習スキップ。"))
            return

        qs = DeliveryRecord.objects.filter(date__gte=since, user_id__in=opted_ids).order_by("-date")
        rows = list(iter_hourly_samples(qs))
        if len(rows) < min_samples:
            self.stdout.write(self.style.WARNING(f"サンプル不足: {len(rows)} < {min_samples}. 学習スキップ。"))
            return

        df = pd.DataFrame(rows)
        # ここではシンプルに3特徴量
        # area_slug -> area_id (整数エンコード)
        slugs = sorted(set(df["area_slug"]))
        slug_to_id = {s:i for i,s in enumerate(slugs)}
        df["area_id"] = df["area_slug"].map(slug_to_id).astype(np.int32)
        df["dow"] = df["dow"].astype(np.int32)
        df["hour"] = df["hour"].astype(np.int32)

        X = df[["dow", "hour", "area_id"]].values
        y = df["y_hourly"].values
        w = df["portion"].values  # レコードの寄与で重み付け

        X_train, X_val, y_train, y_val, w_train, w_val = train_test_split(
            X, y, w, test_size=test_size, random_state=seed
        )

        model = LGBMRegressor(
            n_estimators=600,
            learning_rate=0.05,
            max_depth=-1,
            num_leaves=63,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=seed,
        )
        model.fit(X_train, y_train, sample_weight=w_train, eval_set=[(X_val, y_val)], verbose=False)

        pred_val = model.predict(X_val)
        mae = mean_absolute_error(y_val, pred_val, sample_weight=w_val)
        self.stdout.write(self.style.SUCCESS(f"validation MAE = {mae:.2f} 円/h"))

        # ONNX へ変換
        initial_types = [('x', FloatTensorType([None, X.shape[1]]))]
        onnx_model = skl2onnx.convert_sklearn(model, initial_types=initial_types, target_opset=12)
        onnx_path = "core/ml/model_lgbm.onnx"
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())

        # メタデータ（エンコード辞書など）
        meta = {
            "area_slugs": slugs,
            "feature_order": ["dow", "hour", "area_id"],
            "trained_at": timezone.now().isoformat(),
            "lookback_days": lookback_days,
            "mae_val": float(mae),
        }
        with open("core/ml/model_lgbm.meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Saved ONNX to {onnx_path}"))
        self.stdout.write(self.style.SUCCESS("Done."))
