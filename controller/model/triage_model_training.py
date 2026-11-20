#!/usr/bin/env python3
"""
Host triage model training (XGBoost).

There is no labelled host-telemetry dataset in this repository whose schema
matches the agent events (iface errin/errout/mtu, RDMA qp_errors, dmesg), so by
default the model is trained on a seeded synthetic generator. Its metrics only
show that the pipeline learns the generator's rules; they are NOT real-world
accuracy. Pass ``--events`` with a JSON list of real agent events carrying a
``label`` (0 = normal, 1 = fault) to train on your own data instead.

    python -m controller.model.triage_model_training
    python -m controller.model.triage_model_training --events my_labelled_events.json
"""

import argparse
import json
import os
import random
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split

from controller.features import HOST_FEATURES, extract_host_features
from controller.model.common import MODELS_DIR, binary_metrics, write_card

MODEL_PATH = os.path.join(MODELS_DIR, "xgb_model.joblib")
SEED = 42

_BENIGN_LOGS = ["", "Normal boot messages", "eth0: link is up 25000 Mbps full duplex",
                "systemd[1]: Started Session 3 of user root.", "IPv6: ADDRCONF(NETDEV_CHANGE): eth0: link becomes ready"]


def generate_synthetic_events(n: int = 6000, seed: int = SEED, label_noise: float = 0.02) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    events = []
    for i in range(n):
        nics = ["eth0"] + (["eth1"] if rng.random() < 0.3 else [])
        base_mtu = rng.choice([1500, 1500, 9000])
        ifaces = {nic: {"rx_bytes": rng.randint(10**3, 10**9), "tx_bytes": rng.randint(10**3, 10**9),
                        "errin": rng.choice([0, 0, 0, 1, 2]), "errout": rng.choice([0, 0, 0, 1]), "mtu": base_mtu}
                  for nic in nics}
        rdma = {"qp_errors": 0, "rq_errors": 0}
        dmesg = rng.choice(_BENIGN_LOGS)
        fault = rng.choice(["NORMAL", "NORMAL", "IFACE_ERROR", "MTU", "RDMA", "DRIVER", "LINK", "PANIC"])
        nic = nics[0]
        if fault == "IFACE_ERROR":
            ifaces[nic]["errout"] = rng.randint(5, 500)
            dmesg = rng.choice([f"{nic}: TX errors detected", ""])
        elif fault == "MTU":
            ifaces[nic]["mtu"] = rng.choice([1400, 4200, 9216, 1500 if base_mtu == 9000 else 9000])
            ifaces[nic]["errin"] = rng.randint(0, 300)
            dmesg = rng.choice([f"{nic}: MTU mismatch detected", f"{nic}: frame length exceeds MTU", ""])
        elif fault == "RDMA":
            rdma["qp_errors"] = rng.randint(1, 20)
            dmesg = rng.choice(["mlx5_core: RDMA QP reset or qp error", "infiniband mlx5_0: retry exceeded", ""])
        elif fault == "DRIVER":
            dmesg = rng.choice(["driver: kernel oops - stack trace", "mlx5_core: firmware fatal error"])
            ifaces[nic]["errout"] = rng.randint(0, 50)
        elif fault == "LINK":
            dmesg = f"{nic}: link is down"
            ifaces[nic]["errin"] = rng.randint(0, 40)
        elif fault == "PANIC":
            dmesg = "Kernel panic - not syncing: Fatal exception"
        label = 0 if fault == "NORMAL" else 1
        if rng.random() < label_noise:
            label = 1 - label
        events.append({"event_id": f"synthetic-train-{i}", "host": f"node{rng.randint(1, 5)}", "ifaces": ifaces,
                       "rdma": rdma, "dmesg_tail": dmesg, "label": label, "fault": fault})
    return events


def train_model(events_path: Optional[str] = None) -> str:
    """Train the host triage model. Returns a one-line summary (used by /api/train)."""
    if events_path:
        with open(events_path, encoding="utf-8") as fh:
            events = [e for e in json.load(fh) if isinstance(e, dict) and e.get("label") in (0, 1)]
        if len(events) < 50:
            raise ValueError(f"{events_path}: need >= 50 events with label 0/1, found {len(events)}")
        source = {"type": "user-labelled", "path": events_path}
    else:
        events = generate_synthetic_events()
        source = {"type": "synthetic", "generator": "controller.model.triage_model_training", "seed": SEED,
                  "label_noise": 0.02}

    X = np.vstack([extract_host_features(e) for e in events])
    y = np.array([int(e["label"]) for e in events])
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)
    X_va, X_te, y_va, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5, random_state=SEED, stratify=y_tmp)

    params = {"objective": "binary:logistic", "eval_metric": "logloss", "max_depth": 4, "eta": 0.1,
              "subsample": 0.9, "colsample_bytree": 0.9, "seed": SEED}
    dtr = xgb.DMatrix(X_tr, label=y_tr, feature_names=HOST_FEATURES)
    dva = xgb.DMatrix(X_va, label=y_va, feature_names=HOST_FEATURES)
    bst = xgb.train(params, dtr, num_boost_round=300, evals=[(dva, "validation")],
                    early_stopping_rounds=20, verbose_eval=False)
    prob = bst.predict(xgb.DMatrix(X_te, feature_names=HOST_FEATURES),
                       iteration_range=(0, bst.best_iteration + 1))
    test = binary_metrics(y_te, prob)

    card = {
        "artifact": os.path.basename(MODEL_PATH),
        "task": "host event fault vs normal (priority_score = P(fault))",
        "data": source,
        "features": HOST_FEATURES,
        "rows": {"train": int(len(y_tr)), "validation": int(len(y_va)), "test": int(len(y_te))},
        "best_iteration": int(bst.best_iteration),
        "metrics": {"test": test},
        "caveats": ([
            "Trained on synthetic events: metrics measure agreement with the generator, not real-world accuracy.",
            "Used only as a triage priority signal; every remediation still goes through the shared policy "
            "and human approval.",
        ] if source["type"] == "synthetic" else [
            "Random split of user-provided events; check for temporal/host leakage before trusting metrics."]),
    }
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"booster": bst, "features": HOST_FEATURES, "card": card}, MODEL_PATH)
    write_card("xgb_model", card)
    return (f"Host triage model ({source['type']} data): test F1={test['f1']} on {test['n']} events "
            f"({test['positives']} faults). Saved {MODEL_PATH}.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--events", help="JSON list of agent events with label 0/1 (default: synthetic generator)")
    args = p.parse_args()
    print(train_model(args.events))


if __name__ == "__main__":
    main()
