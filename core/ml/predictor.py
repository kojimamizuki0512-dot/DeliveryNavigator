import os
import json
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None  # onnxruntime 未インストール時は None

from core.areas import AREAS_BY_SLUG

MODEL_ONNX = os.path.join(os.path.dirname(__file__), "model_lgbm.onnx")
MODEL_META = os.path.join(os.path.dirname(__file__), "model_lgbm.meta.json")


class LgbmPredictor:
    """
    ONNX LightGBM 推論（lazy-load）
    - predict_for_all(dow:int, hour:int) -> {slug: float_hourly}
    """
    _session = None
    _slug_list = None

    @classmethod
    def available(cls) -> bool:
        return ort is not None and os.path.exists(MODEL_ONNX) and os.path.exists(MODEL_META)

    @classmethod
    def _ensure_loaded(cls):
        if cls._session is not None:
            return
        if not cls.available():
            raise RuntimeError("ONNX model or meta not available")
        with open(MODEL_META, "r", encoding="utf-8") as f:
            meta = json.load(f)
        cls._slug_list = meta["area_slugs"]
        providers = ["CPUExecutionProvider"]
        cls._session = ort.InferenceSession(MODEL_ONNX, providers=providers)

    @classmethod
    def predict_for_all(cls, dow: int, hour: int) -> dict:
        """
        すべてのエリア slug に対して予測値（円/h）を返す。
        """
        cls._ensure_loaded()
        slugs = cls._slug_list
        area_ids = np.arange(len(slugs), dtype=np.float32)

        X = np.stack([
            np.full_like(area_ids, float(dow), dtype=np.float32),
            np.full_like(area_ids, float(hour), dtype=np.float32),
            area_ids.astype(np.float32)
        ], axis=1)

        outputs = cls._session.run(None, {"x": X})[0].reshape(-1)
        result = {}
        for i, slug in enumerate(slugs):
            if slug in AREAS_BY_SLUG:
                result[slug] = float(outputs[i])
        return result
