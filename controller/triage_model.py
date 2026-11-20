#!/usr/bin/env python3
"""
ML Triage Engine
----------------

Loads the XGBoost host-triage model trained by
``controller/model/triage_model_training.py`` and scores one telemetry event.

- Input: the fixed-length host feature vector from ``controller.features``.
- Output: ``priority_score`` = model probability that the event is a fault,
  plus ``localization`` (the event host).

The model artifact stores its feature names; an artifact trained on a different
feature layout is refused (fallback score 0.1) instead of being mis-applied.
Set ``NBT_TRIAGE_MODEL_PATH=none`` to disable the model (deterministic tests).
"""

import logging
import os
from typing import Any, Dict, Optional

<<<<<<< HEAD
=======
import joblib
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
import numpy as np

from controller.features import HOST_FEATURES, extract_host_features

LOG = logging.getLogger("nbt.triage_model")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "xgb_model.joblib")
FALLBACK_SCORE = 0.1


class TriageModel:
    def __init__(self, model_path: Optional[str] = None):
        path = model_path or os.environ.get("NBT_TRIAGE_MODEL_PATH") or MODEL_PATH
        self.model = None
        self.card: Dict[str, Any] = {}
        self.status = "not_trained"
        if path.lower() == "none":
            self.status = "disabled"
            return
        if not os.path.exists(path):
            return
        try:
<<<<<<< HEAD
            import joblib

=======
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
            obj = joblib.load(path)
        except Exception:
            LOG.exception("Could not load triage model %s", path)
            self.status = "load_error"
            return
        if isinstance(obj, dict) and obj.get("features") == HOST_FEATURES:
            self.model = obj["booster"]
            self.card = obj.get("card", {})
            self.status = "loaded"
        else:
            LOG.warning("Triage model %s has an incompatible feature layout; retrain with "
                        "python -m controller.model.triage_model_training", path)
            self.status = "incompatible"

    def extract_features(self, event: Dict[str, Any], log_embedding: Any = None) -> np.ndarray:
        return extract_host_features(event)

    def predict(self, event: Dict[str, Any], log_embedding: Any = None) -> Dict[str, Any]:
        host = event.get("host", "unknown")
        if self.model is None:
            return {"priority_score": FALLBACK_SCORE, "localization": host, "model": self.status}
        try:
            import xgboost as xgb

            X = xgb.DMatrix(self.extract_features(event).reshape(1, -1), feature_names=HOST_FEATURES)
            score = float(np.asarray(self.model.predict(X)).ravel()[0])
            return {"priority_score": score, "localization": host, "model": "xgb-host"}
        except Exception:
            LOG.exception("Triage model prediction failed; using fallback score")
            return {"priority_score": FALLBACK_SCORE, "localization": host, "model": "error"}


# Self-test
if __name__ == "__main__":
    model = TriageModel()
    fake_event = {"host": "vm-01", "ifaces": {"eth0": {"rx_bytes": 1000, "errin": 10, "errout": 2}}, "rdma": {"qp_errors": 1}}
    print(model.status, model.predict(fake_event))
