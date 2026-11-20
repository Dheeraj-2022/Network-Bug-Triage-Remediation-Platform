"""
Fixed-length host feature vector shared by triage-model training and inference.

Training and serving must use exactly this function; the feature names are
stored with the model so a mismatched model is refused instead of silently
mis-scoring.
"""

import math
import re
from typing import Any, Dict, List

import numpy as np

HOST_FEATURES: List[str] = [
    "iface_count",
    "rx_bytes_log",
    "tx_bytes_log",
    "errin_sum",
    "errout_sum",
    "iface_err_max",
    "mtu_min",
    "mtu_max",
    "mtu_nonstandard",
    "qp_errors",
    "rq_errors",
    "log_mtu",
    "log_rdma",
    "log_driver",
    "log_panic",
    "log_link",
]

_LOG_FLAGS = [
    re.compile(r"\bmtu\b|frame length|length error|oversiz", re.I),
    re.compile(r"\bqp\b|infiniband|rdma|retry", re.I),
    re.compile(r"oops|call trace|driver|firmware", re.I),
    re.compile(r"panic", re.I),
    re.compile(r"link (is )?(down|up)|flap", re.I),
]


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def extract_host_features(event: Dict[str, Any]) -> np.ndarray:
    ifaces = event.get("ifaces") or {}
    rdma = event.get("rdma") or {}
    errin = [_num(s.get("errin")) for s in ifaces.values()]
    errout = [_num(s.get("errout")) for s in ifaces.values()]
    mtus = [_num(s.get("mtu")) for s in ifaces.values() if s.get("mtu") is not None]
    log = event.get("dmesg_tail") or ""
    vec = [
        len(ifaces),
        math.log1p(sum(_num(s.get("rx_bytes")) for s in ifaces.values())),
        math.log1p(sum(_num(s.get("tx_bytes")) for s in ifaces.values())),
        sum(errin),
        sum(errout),
        max((a + b for a, b in zip(errin, errout)), default=0.0),
        min(mtus, default=0.0),
        max(mtus, default=0.0),
        float(any(m not in (1500.0, 9000.0) for m in mtus)),
        _num(rdma.get("qp_errors")),
        _num(rdma.get("rq_errors")),
    ] + [float(bool(rx.search(log))) for rx in _LOG_FLAGS]
    return np.asarray(vec, dtype=float)
