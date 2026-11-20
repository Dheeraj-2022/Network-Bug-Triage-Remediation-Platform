"""
Kernel/system log-line anomaly scorer (XGBoost over hashed n-grams).

Trained by ``controller/model/log_anomaly_training.py`` on the labelled BGL
(BlueGene/L) log. The score is a **model-generated** signal that is shown next
to the deterministic evidence; it never drives remediation. BGL RAS messages
differ from Linux dmesg, so treat cross-domain scores as indicative only.
Set ``NBT_LOG_ANOMALY_MODEL_PATH=none`` to disable.
"""

import logging
import os
import re
from typing import Any, Dict, Optional

import numpy as np

LOG = logging.getLogger("nbt.log_anomaly")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "log_anomaly_xgb.joblib")
NORMALIZER_VERSION = 1

_HEX = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{8,}\b")
_NUM = re.compile(r"\b\d+(\.\d+)*\b")
_WS = re.compile(r"\s+")


def normalize(line: str) -> str:
    s = line.lower()
    s = _HEX.sub(" <hex> ", s)
    s = _NUM.sub(" <num> ", s)
    return _WS.sub(" ", s).strip()


def make_vectorizer():
    from sklearn.feature_extraction.text import HashingVectorizer

    return HashingVectorizer(n_features=2 ** 18, ngram_range=(1, 2), alternate_sign=False,
                             token_pattern=r"<\w+>|[a-z_][a-z_]+", norm="l2")


class LogAnomalyModel:
    def __init__(self, path: Optional[str] = None):
        path = path or os.environ.get("NBT_LOG_ANOMALY_MODEL_PATH") or MODEL_PATH
        self.booster = None
        self.card: Dict[str, Any] = {}
        self.threshold = 0.5
        self.status = "not_trained"
        if path.lower() == "none":
            self.status = "disabled"
            return
        if not os.path.exists(path):
            return
        try:
            import joblib

            obj = joblib.load(path)
            if obj.get("normalizer_version") != NORMALIZER_VERSION:
                self.status = "incompatible"
                return
            self.booster, self.card = obj["booster"], obj.get("card", {})
            self.threshold = float(obj.get("threshold", 0.5))
            self.vectorizer = make_vectorizer()
            self.status = "loaded"
        except Exception:
            LOG.exception("Could not load log anomaly model %s", path)
            self.status = "load_error"

    def score(self, text: str) -> Optional[Dict[str, Any]]:
        lines = [ln for ln in (text or "").splitlines() if ln.strip()]
        if self.booster is None or not lines:
            return None
        import xgboost as xgb

        probs = self.booster.predict(xgb.DMatrix(self.vectorizer.transform([normalize(ln) for ln in lines])))
        probs = np.asarray(probs, dtype=float)
        top = int(probs.argmax())
        return {
            "label": "model-generated",
            "model": "log_anomaly_xgb",
            "trained_on": self.card.get("data", {}).get("dataset", "BGL"),
            "max_score": round(float(probs[top]), 4),
            "threshold": self.threshold,
            "flagged": bool(probs[top] >= self.threshold),
            "top_line": lines[top],
            "lines": [{"line": ln, "score": round(float(p), 4)} for ln, p in zip(lines, probs)],
            "note": "Learned from BlueGene/L RAS logs; indicative only on Linux dmesg. Not used by the "
                    "remediation policy.",
        }


_MODEL: Optional[LogAnomalyModel] = None


def get_log_anomaly_model() -> LogAnomalyModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = LogAnomalyModel()
    return _MODEL
