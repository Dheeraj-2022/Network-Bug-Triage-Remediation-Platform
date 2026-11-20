#!/usr/bin/env python3
"""
Golden-scenario benchmark for the Linux/RDMA MVP.

Every scenario is a hand-written, deterministic fixture run through the real
triage service (rules + log classifier + ML fallback + topology evidence +
shared remediation policy; AI layer off). Scores below measure agreement with
these fixtures only. They are NOT real-world accuracy figures.

Run:
    python -m unittest tests.test_golden_scenarios -v
    python -m tests.test_golden_scenarios          # prints the scenario report
"""

import unittest

from tests.support import event, make_service

# name, events (last one is evaluated), expectations
GOLDEN = [
    {
        "name": "demo_two_host_mtu",
        "demo": True,
        "expect": {"domain": "MTU_MISMATCH", "host": "gpu-b", "iface": "ens1f0", "peer": "leaf-1 Ethernet2",
                   "action": "set_mtu", "status": "pending_approval", "confidence": "high"},
    },
    {
        "name": "lab_mtu_mismatch_peer_unknown",
        "events": [event("node2", mtu=9000, errin=8, dmesg="eth0: MTU mismatch detected")],
        "expect": {"domain": "MTU_MISMATCH", "host": "node2", "iface": "eth0", "peer": None,
                   "action": "set_mtu", "status": "pending_approval", "confidence": "medium"},
    },
    {
        "name": "lab_driver_fault",
        "events": [event("node3", errout=12, dmesg="eth0: TX errors detected; driver reports packet drop")],
        "expect": {"domain": "DRIVER_FAULT", "host": "node3", "iface": "eth0", "peer": None,
                   "action": "restart_driver", "status": "pending_approval"},
    },
    {
        "name": "rdma_errors_out_of_scope_action",
        "events": [event("node4", qp=3, dmesg="mlx5_core: RDMA QP reset or qp error")],
        "expect": {"domain": "RDMA_ERROR", "host": "node4", "iface": None, "peer": None,
                   "action": None, "status": "blocked"},
    },
    {
        "name": "unknown_host_rejected",
        "events": [event("vm-99", mtu=1400, errout=20, dmesg="eth0: MTU mismatch detected")],
        "expect": {"domain": "MTU_MISMATCH", "host": None, "iface": "eth0", "peer": None,
                   "action": None, "status": "blocked", "confidence": "low"},
    },
    {
        "name": "kernel_panic_no_action",
        "events": [event("node5", dmesg="Kernel panic - not syncing: Fatal exception")],
        "expect": {"domain": "KERNEL_PANIC", "host": "node5", "iface": None, "peer": None,
                   "action": None, "status": None},
    },
]


def run_scenario(sc):
    svc = make_service()
    if sc.get("demo"):
        out, code = svc.run_demo("pass")
        assert code == 200
        dec = out["decision"]
    else:
        dec = None
        for ev in sc["events"]:
            dec = svc.process_single(dict(ev))
    ev_ = dec["evidence"]
    loc = ev_["localization"]
    ifaces = loc["interfaces"]
    peer = next((i["peer"] for i in ifaces if i["peer"].get("resolved")), None)
    rem = svc.policy.get(dec["remediation_id"]) if dec.get("remediation_id") else None
    return {
        "domain": ev_["inference"]["fault_domain"],
        "host": loc["host"]["name"] if loc["host"]["resolved"] else None,
        "iface": ifaces[0]["name"] if ifaces else None,
        "peer": f"{peer['device']} {peer['port']}" if peer else None,
        "action": ((rem or {}).get("preview") or {}).get("action"),
        "status": (rem or {}).get("status"),
        "confidence": ev_["confidence"]["level"],
    }


def report():
    dims = ["domain", "host", "iface", "peer", "action", "status", "confidence"]
    totals = {d: [0, 0] for d in dims}
    rows = []
    for sc in GOLDEN:
        got = run_scenario(sc)
        ok_all = True
        for d in dims:
            if d not in sc["expect"]:
                continue
            totals[d][1] += 1
            hit = got[d] == sc["expect"][d]
            totals[d][0] += hit
            ok_all &= hit
        rows.append((sc["name"], ok_all, got))
    return rows, totals


class GoldenScenarioTests(unittest.TestCase):
    def test_each_golden_scenario(self):
        for sc in GOLDEN:
            with self.subTest(scenario=sc["name"]):
                got = run_scenario(sc)
                for key, want in sc["expect"].items():
                    self.assertEqual(got[key], want, f"{sc['name']}: {key}")

    def test_unrelated_recent_change_not_attributed(self):
        out, _ = make_service().run_demo("pass")
        items = {c["change_id"]: c for c in out["decision"]["evidence"]["change_correlation"]["items"]}
        self.assertEqual(items["CHG-DEMO-001"]["relevance"], "relevant")
        # CHG-DEMO-002 is the most recent change, yet it is not on the path and not MTU-related.
        self.assertLess(items["CHG-DEMO-001"]["ts"], items["CHG-DEMO-002"]["ts"])
        self.assertEqual(items["CHG-DEMO-002"]["relevance"], "unrelated")
        self.assertIn("not proof of causation", out["decision"]["evidence"]["change_correlation"]["note"])

    def test_simulated_evidence_is_labelled(self):
        out, _ = make_service().run_demo("pass")
        ev = out["decision"]["evidence"]
        self.assertTrue(ev["simulated"])
        self.assertTrue(all(f["source"].get("simulated") for f in ev["observed_facts"]
                            if f["source"]["type"] in ("telemetry", "log")))
        self.assertTrue(any("SIMULATED" in lim for lim in ev["confidence"]["limitations"]))


if __name__ == "__main__":
    rows, totals = report()
    print("Golden scenarios (synthetic fixtures; not real-world accuracy)\n")
    for name, ok, got in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<36} {got}")
    print("\nPer-dimension agreement with fixtures:")
    for d, (hit, n) in totals.items():
        print(f"  {d:<11} {hit}/{n}")
    passed = sum(1 for _, ok, _ in rows if ok)
    print(f"\nScenarios fully correct: {passed}/{len(rows)}")
