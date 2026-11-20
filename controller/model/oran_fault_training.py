#!/usr/bin/env python3
"""
DeepORAN backhaul-impairment detector (XGBoost).

Trains a binary classifier for ``fault_active`` (Linux tc-netem backhaul delay
or loss injected in the OAI testbed) from per-row measured KPIs of the DeepORAN
Genuine OAI RFsim dataset (``data/DeepOran/deeporan_oai_{train,validation,test}.parquet``).

Leakage controls:
* uses the dataset's own run-level splits (no scenario run spans two splits);
* excludes identifiers, timestamps, process IDs, sequence numbers, cumulative
  counters, scenario/fault labels, controller metadata and the SLA flag;
* drops features that are all-null or constant in the training split.

This model is about 5G slice telemetry; it is NOT used by the host triage path
(agent events do not carry these KPIs). Results are reported per row, per
scenario and per scenario run.

    python -m controller.model.oran_fault_training
    python -m controller.model.oran_fault_training --max-train-rows 500000
"""

import argparse
import os
import time
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from controller.model.common import MODELS_DIR, ROOT, binary_metrics, write_card

DATA_DIR = os.path.join(ROOT, "data", "DeepOran")
ARTIFACT = "oran_fault_xgb.joblib"
SEED = 42

CANDIDATE_FEATURES: List[str] = [
    "rx_mbps", "tx_mbps", "packet_loss_ratio", "rtt_avg_ms", "rtt_p95_ms", "jitter_ms", "iperf_mbps",
    "traffic_loss_ratio", "rsrp_dbm", "dl_bler", "ul_bler", "dl_mcs", "ul_mcs", "ul_nprb",
    "prb_utilization", "throughput_mbps", "latency_ms", "in_sync", "slice_id",
]
META = ["scenario_id", "scenario_run_id", "fault_active", "fault_type", "timestamp_utc"]
# Trailing-window statistics use only past rows of the same run and slice, so they are
# available to a streaming detector at inference time.
WINDOW_COLUMNS = ["rtt_avg_ms", "latency_ms", "throughput_mbps", "traffic_loss_ratio", "rx_mbps"]


def _add_window_features(df: pd.DataFrame, window: int):
    df = df.sort_values(["scenario_run_id", "slice_id", "timestamp_utc"], kind="stable").reset_index(drop=True)
    g = df.groupby(["scenario_run_id", "slice_id"], sort=False)
    names = []
    for col in WINDOW_COLUMNS:
        for stat in ("mean", "std"):
            name = f"{col}_w{window}_{stat}"
            df[name] = g[col].transform(lambda s, st=stat: getattr(s.rolling(window, min_periods=1), st)())
            names.append(name)
    return df, names


def _load(split: str, data_dir: str) -> pd.DataFrame:
    import pyarrow.parquet as pq

    path = os.path.join(data_dir, f"deeporan_oai_{split}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found; download the DeepORAN Parquet files (see README 'Datasets')")
    df = pq.read_table(path, columns=CANDIDATE_FEATURES + META).to_pandas()
    df["in_sync"] = df["in_sync"].astype(float)
    df["fault_active"] = df["fault_active"].astype(int)
    return df


def _per_group(df: pd.DataFrame, prob: np.ndarray, key: str) -> Dict[str, Dict]:
    g = df.assign(pred=(prob >= 0.5).astype(int)).groupby(key)
    return {str(k): {"rows": int(len(v)), "true_fault_rate": round(float(v.fault_active.mean()), 4),
                     "predicted_fault_rate": round(float(v.pred.mean()), 4)} for k, v in g}


def _run_level(df: pd.DataFrame, prob: np.ndarray) -> Dict:
    runs = df.assign(pred=(prob >= 0.5).astype(int)).groupby("scenario_run_id").agg(
        truth=("fault_active", "max"), flagged=("pred", "mean"))
    return binary_metrics(runs.truth.values, runs.flagged.values, threshold=0.5)


def train(data_dir: str = DATA_DIR, max_train_rows: int = 2_000_000, window: int = 64) -> str:
    t0 = time.time()
    tr, va, te = (_load(s, data_dir) for s in ("train", "validation", "test"))
    feats = [c for c in CANDIDATE_FEATURES if tr[c].notna().any() and tr[c].nunique(dropna=True) > 1]
    dropped = sorted(set(CANDIDATE_FEATURES) - set(feats))
    if window > 1:
        (tr, wnames), (va, _), (te, _) = (_add_window_features(d, window) for d in (tr, va, te))
        feats += wnames
    full_train_rows = len(tr)
    if len(tr) > max_train_rows:
        tr = tr.sample(n=max_train_rows, random_state=SEED)

    pos = int(tr.fault_active.sum())
    params = {"objective": "binary:logistic", "eval_metric": ["logloss", "aucpr"], "tree_method": "hist",
              "max_depth": 6, "eta": 0.1, "subsample": 0.8, "colsample_bytree": 0.8, "seed": SEED,
              "scale_pos_weight": (len(tr) - pos) / max(pos, 1), "nthread": os.cpu_count() or 4}
    dtr = xgb.DMatrix(tr[feats], label=tr.fault_active, feature_names=feats)
    dva = xgb.DMatrix(va[feats], label=va.fault_active, feature_names=feats)
    bst = xgb.train(params, dtr, num_boost_round=400, evals=[(dva, "validation")],
                    early_stopping_rounds=25, verbose_eval=50)
    it = (0, bst.best_iteration + 1)
    p_va = bst.predict(dva, iteration_range=it)
    p_te = bst.predict(xgb.DMatrix(te[feats], feature_names=feats), iteration_range=it)

    gain = bst.get_score(importance_type="gain")
    card = {
        "artifact": ARTIFACT,
        "task": "DeepORAN row-level backhaul impairment detection (fault_active)",
        "data": {"dataset": "DeepORAN Genuine OAI RFsim Closed-Loop Telemetry (v2)", "path": data_dir,
                 "splits": "dataset-provided, split by scenario_run_id",
                 "rows_available": {"train": full_train_rows, "validation": len(va), "test": len(te)},
                 "train_rows_used": len(tr), "train_sampling": f"uniform random, seed {SEED}"},
        "features": feats,
        "window_rows": window,
        "dropped_features": dropped,
        "fault_scenarios_by_split": {name: sorted(d.loc[d.fault_active == 1, "scenario_id"].unique().tolist())
                                     for name, d in (("train", tr), ("validation", va), ("test", te))},
        "best_iteration": int(bst.best_iteration),
        "metrics": {
            "validation_rows": binary_metrics(va.fault_active.values, p_va),
            "test_rows": binary_metrics(te.fault_active.values, p_te),
            "test_runs": _run_level(te, p_te),
            "test_by_scenario": _per_group(te, p_te, "scenario_id"),
        },
        "feature_importance_gain": {k: round(v, 2) for k, v in sorted(gain.items(), key=lambda kv: -kv[1])},
        "caveats": [
            "RFsim software radio channel, not over-the-air RF; one testbed and one OAI commit.",
            "Fault scenarios also use specific traffic workloads, so the model may partly learn the workload "
            "rather than the impairment; check test_by_scenario false-positive rates.",
            "Rows within a run are temporally correlated; run-level metrics have a small denominator.",
            "Not wired into host triage: agent events do not contain these KPIs.",
        ],
        "train_seconds": round(time.time() - t0, 1),
    }
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"booster": bst, "features": feats, "card": card}, os.path.join(MODELS_DIR, ARTIFACT))
    write_card("oran_fault_xgb", card)
    m, r = card["metrics"]["test_rows"], card["metrics"]["test_runs"]
    return (f"DeepORAN fault detector: test rows F1={m['f1']} AUC={m['roc_auc']} (n={m['n']}, "
            f"faults={m['positives']}); test runs {r['confusion']} (n={r['n']}).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=DATA_DIR)
    p.add_argument("--max-train-rows", type=int, default=2_000_000)
    p.add_argument("--window", type=int, default=64, help="trailing rows per run/slice for window features (1 = off)")
    a = p.parse_args()
    print(train(a.data_dir, a.max_train_rows, a.window))


if __name__ == "__main__":
    main()
