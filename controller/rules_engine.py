#!/usr/bin/env python3
"""
Rule-Based Triage Engine
------------------------

Provides a simple, deterministic triage system for network telemetry events.
Acts as a fallback / baseline to ML-based triage.

Logic:
- Check for interface errors (errin/errout).
- Check for RDMA errors (qp_errors, rq_errors).
- If thresholds exceeded, mark event for remediation.

Event schema (input):
{
  "event_id": "...",
  "host": "vm-01",
  "ts": "2025-10-04T12:34:56.789Z",
  "ifaces": { "eth0": { "errin": 5, "errout": 2, ... } },
  "rdma": { "qp_errors": 1, "rq_errors": 0 },
  "dmesg_tail": "... logs ..."
}

Return schema (output):
{
  "action": "remediate" | "none",
  "reason": "<string>",
  "targets": [{"host": "vm-01", "iface": "eth0"}]
}
"""

from typing import Dict, Any, List


def rule_based_triage(event: Dict[str, Any],
                      iface_err_threshold: int = 5,
                      rdma_err_threshold: int = 1) -> Dict[str, Any]:
    targets: List[Dict[str, Any]] = []
    reasons = []

    # Check interface stats
    for nic, stats in event.get("ifaces", {}).items():
        err_sum = int(stats.get("errin", 0)) + int(stats.get("errout", 0))
        if err_sum >= iface_err_threshold:
            targets.append({"host": event["host"], "iface": nic, "err_sum": err_sum})
            reasons.append(f"{nic} iface errors={err_sum}")

    # Check RDMA stats
    rdma = event.get("rdma", {})
    if int(rdma.get("qp_errors", 0)) >= rdma_err_threshold:
        targets.append({"host": event["host"], "component": "rdma_qp"})
        reasons.append("RDMA QP errors exceeded")

    if targets:
        return {"action": "remediate", "reason": "; ".join(reasons), "targets": targets}
    else:
        return {"action": "none", "reason": "no rule triggered", "targets": []}


# Quick self-test
if __name__ == "__main__":
    sample_event = {
        "event_id": "123",
        "host": "vm-01",
        "ifaces": {"eth0": {"errin": 2, "errout": 6}},
        "rdma": {"qp_errors": 0}
    }
    print(rule_based_triage(sample_event))
