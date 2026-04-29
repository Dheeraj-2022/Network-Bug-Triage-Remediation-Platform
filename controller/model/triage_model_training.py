# triage_model_training.py

"""
Triage Model Training Script

This script trains the ML triage engine for the Network Bug Triage & Remediation Platform.

Steps:
1. Load or generate synthetic telemetry events (data/sample_events.json).
2. Extract features: interface stats, RDMA counters, dmesg log embeddings.
3. Train an XGBoost classifier to detect and localize faults.
4. Evaluate accuracy.
5. Save model (controller/models/xgb_model.joblib).
"""

import os
import json
import random
import numpy as np
import joblib
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

try:
    from sentence_transformers import SentenceTransformer
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    embed_model = None

# Paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PATH = os.path.join(ROOT, "data", "sample_events.json")
MODEL_PATH = os.path.join(ROOT, "controller", "models", "xgb_model.joblib")


# --------------------------
# Generate Synthetic Events
# --------------------------
def generate_synthetic_events(n=200):
    hosts = [f"node{i+1}" for i in range(5)]
    fault_types = ["MTU_MISMATCH", "IFACE_ERROR", "RDMA_QP", "DRIVER_OOPS", "NORMAL"]
    events = []
    for i in range(n):
        host = random.choice(hosts)
        fault = random.choice(fault_types)
        ifaces = {
            "eth0": {
                "rx_bytes": random.randint(1e3, 1e6),
                "tx_bytes": random.randint(1e3, 1e6),
                "errin": 0,
                "errout": 0,
                "mtu": 1500,
            }
        }
        rdma = {"qp_errors": 0}
        dmesg = "normal boot"
        label = "none"

        if fault == "IFACE_ERROR":
            ifaces["eth0"]["errout"] = random.randint(5, 20)
            dmesg = "eth0: TX errors detected"
            label = host
        elif fault == "MTU_MISMATCH":
            ifaces["eth0"]["mtu"] = random.choice([1400, 9000])
            dmesg = "MTU mismatch detected"
            label = host
        elif fault == "RDMA_QP":
            rdma["qp_errors"] = random.randint(1, 5)
            dmesg = "mlx5_core: qp error"
            label = host
        elif fault == "DRIVER_OOPS":
            dmesg = "kernel oops - stack trace"
            label = host

        events.append(
            {"host": host, "ifaces": ifaces, "rdma": rdma, "dmesg_tail": dmesg, "label": label}
        )
    return events


# --------------------------
# Feature Extraction
# --------------------------
def featurize(events):
    if embed_model:
        _embed = embed_model
    else:
        _embed = None
    X, y = [], []
    for ev in events:
        iface = ev["ifaces"]["eth0"]
        feat = [
            iface["rx_bytes"],
            iface["tx_bytes"],
            iface["errin"],
            iface["errout"],
            iface["mtu"],
            ev["rdma"]["qp_errors"],
        ]
        text = ev.get("dmesg_tail", "")
        if _embed:
            emb = _embed.encode([text])[0]
        else:
            emb = np.array([hash(text) % 100 / 100.0] * 16)
        feat = np.concatenate([np.array(feat), np.array(emb)])
        X.append(feat)
        y.append(0 if ev["label"] == "none" else 1)
    return np.vstack(X), np.array(y)


def train_model():
    """Train the XGBoost triage model. Returns a summary string."""
    # Load or generate events
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            events = json.load(f)
    else:
        events = generate_synthetic_events(300)
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH, "w") as f:
            json.dump(events, f, indent=2)

    print(f"Loaded {len(events)} events.")

    X, y = featurize(events)
    print("Feature matrix shape:", X.shape, "Labels shape:", y.shape)

    # Train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)

    params = {"objective": "binary:logistic", "eval_metric": "logloss"}
    bst = xgb.train(params, dtrain, num_boost_round=50, evals=[(dtest, "test")], verbose_eval=False)

    # Evaluate
    preds = (bst.predict(dtest) > 0.5).astype(int)
    report = classification_report(y_test, preds)
    print("\nClassification Report:")
    print(report)

    # Save
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(bst, MODEL_PATH)
    print("Saved model to", MODEL_PATH)

    acc = (preds == y_test).mean()
    return f"Accuracy={acc:.2%} on {len(X_test)} test samples. Model saved."


if __name__ == "__main__":
    train_model()
