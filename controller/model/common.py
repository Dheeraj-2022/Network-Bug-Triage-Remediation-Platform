"""Shared helpers for model training scripts: metrics and model cards."""

import json
import os
import platform
from datetime import datetime, timezone
from typing import Any, Dict

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS_DIR = os.path.join(ROOT, "controller", "models")


def binary_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    pred = (np.asarray(prob) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    out = {
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
        "threshold": threshold,
        "accuracy": round(float((pred == y_true).mean()), 4) if len(y_true) else None,
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    out["roc_auc"] = (round(float(roc_auc_score(y_true, prob)), 4)
                      if 0 < y_true.sum() < len(y_true) else None)
    return out


def write_card(name: str, card: Dict[str, Any]) -> str:
    os.makedirs(MODELS_DIR, exist_ok=True)
    card = {
        "name": name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        **card,
    }
    path = os.path.join(MODELS_DIR, f"{name}.card.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(card, fh, indent=2, default=str)
    return path


def load_cards() -> Dict[str, Any]:
    cards = {}
    if os.path.isdir(MODELS_DIR):
        for f in sorted(os.listdir(MODELS_DIR)):
            if f.endswith(".card.json"):
                try:
                    with open(os.path.join(MODELS_DIR, f), encoding="utf-8") as fh:
                        card = json.load(fh)
                    artifact = os.path.join(MODELS_DIR, card.get("artifact", ""))
                    card["artifact_present"] = bool(card.get("artifact")) and os.path.exists(artifact)
                    cards[card.get("name", f)] = card
                except (OSError, ValueError):
                    continue
    return cards
