#!/usr/bin/env python3
"""
ML Triage Engine
----------------

Implements an XGBoost classifier for network issue triage.
- Input: Telemetry features (iface stats + RDMA + log embeddings)
- Output: Predicted issue localization + priority score

Model training is handled in `notebooks/triage_training.ipynb`
This file only loads and applies the trained model.
"""

import os
import numpy as np
import joblib
from typing import Dict, Any

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "xgb_model.joblib")


class TriageModel:
    def __init__(self, model_path: str = MODEL_PATH):
        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
        else:
            self.model = None

    def extract_features(self, event: Dict[str, Any], log_embedding: np.ndarray) -> np.ndarray:
        """Convert event + log embedding into ML feature vector."""
        iface_stats = []
        for nic, stats in event.get("ifaces", {}).items():
            iface_stats.extend([
                int(stats.get("rx_bytes", 0)),
                int(stats.get("tx_bytes", 0)),
                int(stats.get("errin", 0)),
                int(stats.get("errout", 0)),
                int(stats.get("mtu", 1500)),
            ])
        rdma = event.get("rdma", {})
        rdma_stats = [int(rdma.get("qp_errors", 0)), int(rdma.get("rq_errors", 0))]
        return np.concatenate([iface_stats, rdma_stats, log_embedding])

    def predict(self, event: Dict[str, Any], log_embedding: np.ndarray) -> Dict[str, Any]:
        if not self.model:
            return {"priority_score": 0.1, "localization": event.get("host", "unknown")}
        X = self.extract_features(event, log_embedding).reshape(1, -1)
        prob = self.model.predict_proba(X)[0].max()
        label = self.model.predict(X)[0]
        return {"priority_score": float(prob), "localization": str(label)}


# Self-test
if __name__ == "__main__":
    model = TriageModel()
    fake_event = {"host": "vm-01", "ifaces": {"eth0": {"rx_bytes": 1000, "errin": 10, "errout": 2}}, "rdma": {"qp_errors": 1}}
    fake_emb = np.random.rand(384)
    print(model.predict(fake_event, fake_emb))
