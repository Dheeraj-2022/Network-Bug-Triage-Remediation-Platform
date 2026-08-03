#!/usr/bin/env python3
"""
Tests for the AI multi-agent layer.

These tests run fully offline (heuristic backend + numpy retrieval) and verify:
  * the orchestrator produces a grounded RCA + guardrailed remediation plan,
  * the human-approval gate holds risky remediations,
  * kernel panics are never auto-remediated,
  * memory records incidents and surfaces failure patterns,
  * backward compatibility: the legacy triage pipeline still runs.

Run:
    python -m tests.test_ai_layer
    # or, if pytest is installed:
    pytest tests/test_ai_layer.py
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _event(host="node1", dmesg="eth0: MTU mismatch detected", qp=2, errout=7, mtu=1400):
    return {
        "event_id": f"evt-{host}-test",
        "host": host,
        "ts": "2026-08-03T00:00:00+00:00",
        "ifaces": {"eth0": {"rx_bytes": 100, "tx_bytes": 100,
                            "errin": 0, "errout": errout, "mtu": mtu}},
        "rdma": {"qp_errors": qp},
        "dmesg_tail": dmesg,
    }


def _base(domain="MTU_MISMATCH", priority=0.9):
    return {
        "rule": {"action": "remediate", "reason": "iface errors",
                 "targets": [{"host": "node1", "iface": "eth0"}]},
        "ml": {"priority_score": priority, "localization": "node1"},
        "log_class": domain,
    }


def test_orchestrator_rca_and_plan():
    from controller.ai import get_orchestrator

    orch = get_orchestrator()
    out = orch.run(_event(), _base())
    rca = out["rca"]
    assert rca.get("fault_domain") == "MTU_MISMATCH"
    assert 0.0 <= float(rca.get("confidence", 0)) <= 1.0
    assert out["remediation"].get("playbook") == "remediate_mtu.yml"
    # Grounded in retrieved knowledge.
    assert out["context_sources"], "expected retrieved context sources"
    print("test_orchestrator_rca_and_plan: OK")


def test_human_approval_gate():
    from controller.ai import get_orchestrator

    orch = get_orchestrator()
    out = orch.run(_event(host="node2"), _base())
    # Default config requires approval.
    assert out["remediation"].get("status") == "pending_approval"
    print("test_human_approval_gate: OK")


def test_kernel_panic_not_autoremediated():
    from controller.ai import get_orchestrator

    orch = get_orchestrator()
    out = orch.run(
        _event(host="node3", dmesg="kernel panic - not syncing; call trace", qp=0),
        _base(domain="KERNEL_PANIC"),
    )
    assert out["remediation"].get("playbook") is None
    assert out["remediation"].get("risk") == "high"
    print("test_kernel_panic_not_autoremediated: OK")


def test_memory_records_incidents():
    from controller.ai.memory import get_memory

    mem = get_memory()
    before = mem.stats()["incidents"]
    mem.record_incident({
        "incident_id": "inc-unit-1", "host": "node9",
        "fault_domain": "DRIVER_FAULT", "playbook": "restart_driver.yml",
        "resolved": True,
    })
    after = mem.stats()["incidents"]
    assert after == before + 1
    patterns = mem.failure_patterns()
    assert "DRIVER_FAULT" in patterns
    print("test_memory_records_incidents: OK")


def test_backward_compatibility_legacy_pipeline():
    # The legacy modules must still import and run.
    from controller.rules_engine import rule_based_triage
    from controller.triage_model import TriageModel
    import numpy as np

    rule = rule_based_triage(_event())
    assert rule["action"] == "remediate"
    model = TriageModel()
    res = model.predict(_event(), np.zeros(384))
    assert "priority_score" in res and "localization" in res
    print("test_backward_compatibility_legacy_pipeline: OK")


def main():
    test_orchestrator_rca_and_plan()
    test_human_approval_gate()
    test_kernel_panic_not_autoremediated()
    test_memory_records_incidents()
    test_backward_compatibility_legacy_pipeline()
    print("\nAll AI-layer tests passed.")


if __name__ == "__main__":
    main()
