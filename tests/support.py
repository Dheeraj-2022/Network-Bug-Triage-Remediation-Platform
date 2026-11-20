"""Shared, deterministic test fixtures (offline: no embeddings model, no AI, in-memory store)."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("NBT_DISABLE_EMBEDDINGS", "1")
os.environ.setdefault("NBT_AI_ENABLED", "0")
# Trained artifacts in controller/models must not change golden/policy expectations.
os.environ.setdefault("NBT_TRIAGE_MODEL_PATH", "none")
os.environ.setdefault("NBT_LOG_ANOMALY_MODEL_PATH", "none")


def make_registry():
    from controller.topology import DEFAULT_TOPOLOGY_DIR, TopologyRegistry

    reg = TopologyRegistry()
    reg.load_dir(DEFAULT_TOPOLOGY_DIR)
    return reg


def make_policy(mode="simulate", **kw):
    from controller.remediation import ProposalStore, RemediationPolicy

    return RemediationPolicy(store=ProposalStore(":memory:"), registry=make_registry(), mode=mode, **kw)


def make_service(policy=None):
    from api.service import TriageService

    return TriageService(policy=policy or make_policy(), enable_ai=False)


def event(host, iface="eth0", errin=0, errout=0, mtu=1500, qp=0, dmesg="", event_id=None,
          ts="2026-01-15T10:00:00+00:00"):
    return {
        "event_id": event_id or f"golden-{host}-{iface}-{mtu}-{errin}-{errout}-{qp}",
        "host": host,
        "ts": ts,
        "ifaces": {iface: {"rx_bytes": 1000, "tx_bytes": 1000, "errin": errin, "errout": errout, "mtu": mtu}},
        "rdma": {"qp_errors": qp, "rq_errors": 0, "srq_errors": 0},
        "dmesg_tail": dmesg,
    }
