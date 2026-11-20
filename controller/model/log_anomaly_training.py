#!/usr/bin/env python3
"""
Log-line anomaly model (XGBoost) trained on the labelled BGL log.

BGL line format: ``<label> <epoch> <date> <node> <time> <node> <type> <component> <level> <message>``;
label ``-`` = non-alert, anything else = alert. Only the free-text message is
used (the severity level and alert tag are excluded) so the model can be applied
to Linux dmesg lines, which have no such fields.

Leakage controls:
* chronological split: the first 80% of lines (by file order) train, the last
  20% test; the last 10% of the training period is used for early stopping;
* duplicate lines are collapsed to (normalized message, label) with counts used
  as sample weights; metrics are reported per line and on test messages whose
  normalized text never appears in training ("unseen").

    python -m controller.model.log_anomaly_training
    python -m controller.model.log_anomaly_training --bgl data/BGL/BGL.log --max-lines 2000000
"""

import argparse
import os
import time
from collections import Counter
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
import xgboost as xgb

from controller.log_anomaly import NORMALIZER_VERSION, make_vectorizer, normalize
from controller.model.common import MODELS_DIR, ROOT, binary_metrics, write_card

BGL_PATH = os.path.join(ROOT, "data", "BGL", "BGL.log")
ARTIFACT = "log_anomaly_xgb.joblib"
SEED = 42


def _parse(line: str) -> Optional[Tuple[int, str]]:
    parts = line.rstrip("\n").split(" ", 9)
    if len(parts) < 10:
        return None
    return (0 if parts[0] == "-" else 1), normalize(parts[9])


def _count_lines(path: str, limit: Optional[int]) -> int:
    n = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for n, _ in enumerate(fh, start=1):
            if limit and n >= limit:
                break
    return n


def _collect(path: str, total: int) -> Dict[str, Counter]:
    cut_test, cut_val = int(total * 0.8), int(total * 0.72)
    buckets = {"train": Counter(), "validation": Counter(), "test": Counter()}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= total:
                break
            parsed = _parse(line)
            if parsed is None:
                continue
            key = "train" if i < cut_val else "validation" if i < cut_test else "test"
            buckets[key][(parsed[1], parsed[0])] += 1
    return buckets


def _matrix(counter: Counter, vec):
    keys = list(counter)
    X = vec.transform([k[0] for k in keys])
    y = np.array([k[1] for k in keys])
    w = np.array([counter[k] for k in keys], dtype=float)
    return X, y, w, keys


def train(bgl_path: str = BGL_PATH, max_lines: Optional[int] = None) -> str:
    if not os.path.exists(bgl_path):
        raise FileNotFoundError(f"{bgl_path} not found; download BGL from loghub (see README 'Datasets')")
    t0 = time.time()
    total = _count_lines(bgl_path, max_lines)
    b = _collect(bgl_path, total)
    vec = make_vectorizer()
    X_tr, y_tr, w_tr, k_tr = _matrix(b["train"], vec)
    X_va, y_va, w_va, _ = _matrix(b["validation"], vec)
    X_te, y_te, w_te, k_te = _matrix(b["test"], vec)

    pos_w = float(w_tr[y_tr == 1].sum())
    params = {"objective": "binary:logistic", "eval_metric": ["logloss", "aucpr"], "tree_method": "hist",
              "max_depth": 6, "eta": 0.2, "seed": SEED, "nthread": os.cpu_count() or 4,
              "scale_pos_weight": float(w_tr[y_tr == 0].sum()) / max(pos_w, 1.0)}
    dtr = xgb.DMatrix(X_tr, label=y_tr, weight=w_tr)
    dva = xgb.DMatrix(X_va, label=y_va, weight=w_va)
    bst = xgb.train(params, dtr, num_boost_round=300, evals=[(dva, "validation")],
                    early_stopping_rounds=20, verbose_eval=50)
    it = (0, bst.best_iteration + 1)
    p_te = bst.predict(xgb.DMatrix(X_te), iteration_range=it)

    # Line-level metrics: expand unique messages by their occurrence counts.
    reps = w_te.astype(int)
    line_metrics = binary_metrics(np.repeat(y_te, reps), np.repeat(p_te, reps))
    seen = {k[0] for k in k_tr} | {k[0] for k in b["validation"]}
    unseen = np.array([k[0] not in seen for k in k_te])
    unseen_metrics = binary_metrics(y_te[unseen], p_te[unseen]) if unseen.any() else None

    card = {
        "artifact": ARTIFACT,
        "task": "log line alert vs non-alert (message text only)",
        "data": {"dataset": "BGL (loghub)", "path": bgl_path, "lines_used": total,
                 "split": "chronological by file order: 72% train / 8% validation / 20% test",
                 "unique_messages": {k: len(v) for k, v in b.items()},
                 "alert_lines": {k: int(sum(c for (m, lbl), c in v.items() if lbl)) for k, v in b.items()}},
        "features": "HashingVectorizer(2^18, word 1-2 grams) over normalized message text",
        "normalizer_version": NORMALIZER_VERSION,
        "best_iteration": int(bst.best_iteration),
        "metrics": {"test_lines": line_metrics, "test_unseen_messages": unseen_metrics,
                    "test_unseen_message_count": int(unseen.sum())},
        "caveats": [
            "BGL alert tags label whole messages; many test lines repeat training messages, so per-line "
            "scores are optimistic. test_unseen_messages is the better generalization estimate.",
            "BlueGene/L RAS logs differ from Linux dmesg; scores on host events are indicative only.",
            "Model output is displayed as a model-generated signal and is not used by the remediation policy.",
            "HPC, Linux and OpenStack logs in data/ were not used: they have no per-line labels in this form.",
        ],
        "train_seconds": round(time.time() - t0, 1),
    }
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"booster": bst, "normalizer_version": NORMALIZER_VERSION, "threshold": 0.5, "card": card},
                os.path.join(MODELS_DIR, ARTIFACT))
    write_card("log_anomaly_xgb", card)
    u = unseen_metrics or {}
    return (f"BGL log anomaly model: test lines F1={line_metrics['f1']} (n={line_metrics['n']}, "
            f"alerts={line_metrics['positives']}); unseen messages F1={u.get('f1')} (n={u.get('n')}).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bgl", default=BGL_PATH)
    p.add_argument("--max-lines", type=int, default=None, help="use only the first N lines (default: all)")
    a = p.parse_args()
    print(train(a.bgl, a.max_lines))


if __name__ == "__main__":
    main()
