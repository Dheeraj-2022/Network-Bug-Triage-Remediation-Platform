#!/usr/bin/env python3
"""
Shared remediation policy: allowlist, target validation, approval gate,
idempotency, execution modes and post-check outcomes.

Run:  python -m unittest tests.test_remediation_policy -v
"""

import copy
import glob
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from tests.support import ROOT, event, make_policy, make_registry


class SpyExecutor:
    def __init__(self, ok=True, raises=False):
        self.calls, self.ok, self.raises = [], ok, raises

    def __call__(self, mode):
        self.mode = mode
        return self

    def run(self, preview):
        self.calls.append(preview)
        if self.raises:
            raise RuntimeError("boom")
        return {"ok": self.ok, "mode": self.mode, "simulated": self.mode == "simulate", "detail": "spy", "phases": []}


def demo_evidence():
    from controller.demo_scenarios import load_mtu_two_host
    from controller.evidence import build_evidence
    from controller.rules_engine import rule_based_triage

    sc = load_mtu_two_host()
    base, peer, trig = sc["telemetry"]
    ev = build_evidence(trig, make_registry(), previous=base, peer_samples=[peer], changes=sc["changes"],
                        rule=rule_based_triage(trig), log_class="MTU_MISMATCH")
    return sc, trig, ev


RULE_MTU = {"recommender": "rules", "playbook": "remediate_mtu.yml",
            "targets": [{"host": "gpu-b", "iface": "ens1f0"}]}


class PolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.sc, self.trig, self.ev = demo_evidence()

    def propose(self, policy, candidates, ev=None, trig=None):
        return policy.propose(source="test", event=trig or self.trig, evidence=ev or self.ev, candidates=candidates)

    def test_valid_mtu_candidate_is_previewed_not_executed(self):
        spy = SpyExecutor()
        p = self.propose(make_policy(executor_factory=spy), [RULE_MTU])
        self.assertEqual(p["status"], "pending_approval")
        prev = p["preview"]
        self.assertEqual(prev["action"], "set_mtu")
        self.assertEqual(prev["targets"], [{"host": "gpu-b", "iface": "ens1f0"}])
        self.assertEqual(prev["extra_vars"], {"targets": [{"host": "gpu-b", "iface": "ens1f0"}], "desired_mtu": 9000})
        self.assertTrue(prev["requires_approval"])
        self.assertTrue(prev["simulated"])
        self.assertIn("--limit gpu-b", prev["command_preview"])
        self.assertTrue(prev["rollback"])
        self.assertEqual(spy.calls, [])

    def test_unknown_playbook_is_rejected(self):
        p = self.propose(make_policy(), [{"recommender": "ai", "playbook": "wipe_disk.yml"}])
        self.assertEqual(p["status"], "blocked")
        self.assertIn("not an allowlisted action", p["block_reason"])

    def test_action_not_applicable_to_domain_is_rejected(self):
        p = self.propose(make_policy(), [{"recommender": "rules", "playbook": "restart_driver.yml"}])
        self.assertEqual(p["status"], "blocked")
        self.assertIn("not applicable to fault domain MTU_MISMATCH", p["block_reason"])

    def test_target_outside_incident_is_rejected(self):
        bad = {**RULE_MTU, "targets": [{"host": "gpu-a", "iface": "ens1f0"}]}
        p = self.propose(make_policy(), [bad])
        self.assertEqual(p["status"], "blocked")
        self.assertIn("outside this incident", p["block_reason"])

    def test_mismatched_interface_is_rejected(self):
        bad = {**RULE_MTU, "targets": [{"host": "gpu-b", "iface": "ens9"}]}
        self.assertEqual(self.propose(make_policy(), [bad])["status"], "blocked")

    def test_unsafe_interface_and_mtu_values_are_rejected(self):
        ev = copy.deepcopy(self.ev)
        ev["remediation_hint"]["targets"] = [{"host": "gpu-b", "iface": "ens1f0;reboot"}]
        self.assertIn("invalid", self.propose(make_policy(), [RULE_MTU], ev=ev)["block_reason"])
        ev = copy.deepcopy(self.ev)
        ev["remediation_hint"]["desired_mtu"] = 65000
        self.assertIn("outside the allowed range", self.propose(make_policy(), [RULE_MTU], ev=ev)["block_reason"])

    def test_set_mtu_requires_confirmed_mismatch(self):
        ev = copy.deepcopy(self.ev)
        ev["remediation_hint"] = None
        self.assertIn("no confirmed MTU mismatch", self.propose(make_policy(), [RULE_MTU], ev=ev)["block_reason"])

    def test_untrusted_model_variables_are_ignored(self):
        ai = {"recommender": "ai", "playbook": "remediate_mtu.yml",
              "extra_vars": {"desired_mtu": 1500, "reason": "$(rm -rf /)"}}
        p = self.propose(make_policy(), [ai])
        self.assertEqual(p["preview"]["extra_vars"]["desired_mtu"], 9000)
        self.assertNotIn("reason", p["preview"]["extra_vars"])
        self.assertIn("extra_vars", p["preview"]["ignored_inputs"])

    def test_ansible_mode_requires_inventory_membership(self):
        p = self.propose(make_policy(mode="ansible", inventory=set()), [RULE_MTU])
        self.assertEqual(p["status"], "blocked")
        self.assertIn("inventory.ini", p["block_reason"])

    def test_invalid_mode_fails_closed(self):
        with self.assertRaises(ValueError):
            make_policy(mode="yolo")


class ApprovalFlowTests(unittest.TestCase):
    def setUp(self):
        self.sc, self.trig, self.ev = demo_evidence()
        self.spy = SpyExecutor()
        self.policy = make_policy(executor_factory=self.spy)
        self.p = self.policy.propose(source="test", event=self.trig, evidence=self.ev, candidates=[RULE_MTU])

    def post(self, variant):
        return lambda _p: self.sc["post_checks"][variant]

    def test_reject_never_executes(self):
        res, code = self.policy.decide(self.p["id"], approved=False, approver="alice")
        self.assertEqual((code, res["status"]), (200, "rejected"))
        self.assertEqual(self.spy.calls, [])

    def test_approve_simulates_then_post_check_passes(self):
        res, code = self.policy.decide(self.p["id"], approved=True, approver="alice",
                                       preview_digest=self.p["preview_digest"], post_telemetry=self.post("pass"))
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "resolved")
        self.assertTrue(res["execution"]["simulated"])
        self.assertEqual(len(self.spy.calls), 1)
        kinds = [a["kind"] for a in self.policy.audit(proposal_id=self.p["id"])]
        self.assertEqual(kinds, ["recommended", "previewed", "approved", "simulated", "post_check"])
        self.assertEqual(self.policy.audit(proposal_id=self.p["id"])[2]["actor"], "alice")

    def test_failed_post_check_is_not_resolved(self):
        res, _ = self.policy.decide(self.p["id"], approved=True, approver="alice", post_telemetry=self.post("fail"))
        self.assertEqual(res["status"], "verification_failed")
        self.assertEqual(res["verification"]["outcome"], "failed")
        failed = [c["name"] for c in res["verification"]["checks"] if c["status"] == "fail"]
        self.assertIn("iface_errors_stable", failed)

    def test_inconclusive_post_check_is_not_resolved(self):
        res, _ = self.policy.decide(self.p["id"], approved=True, approver="alice",
                                    post_telemetry=self.post("inconclusive"))
        self.assertEqual(res["status"], "verification_inconclusive")

    def test_no_post_telemetry_is_inconclusive(self):
        res, _ = self.policy.decide(self.p["id"], approved=True, approver="alice")
        self.assertEqual(res["status"], "verification_inconclusive")

    def test_duplicate_approval_refused_and_executes_once(self):
        self.policy.decide(self.p["id"], approved=True, approver="alice", post_telemetry=self.post("pass"))
        res, code = self.policy.decide(self.p["id"], approved=True, approver="bob")
        self.assertEqual(code, 409)
        self.assertEqual(len(self.spy.calls), 1)

    def test_stale_and_changed_preview_refused(self):
        res, code = self.policy.decide(self.p["id"], approved=True, approver="alice", preview_digest="deadbeef")
        self.assertEqual(code, 409)
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.policy.store.transition(self.p["id"], "pending_approval", {"expires_at": past})
        res, code = self.policy.decide(self.p["id"], approved=True, approver="alice")
        self.assertEqual(code, 409)
        self.assertEqual(self.policy.get(self.p["id"])["status"], "expired")
        self.assertEqual(self.spy.calls, [])

    def test_invalid_approver_refused(self):
        _, code = self.policy.decide(self.p["id"], approved=True, approver="")
        self.assertEqual(code, 400)
        _, code = self.policy.decide(self.p["id"], approved=True, approver="x; rm -rf /")
        self.assertEqual(code, 400)

    def test_executor_failure_is_visible(self):
        spy = SpyExecutor(raises=True)
        pol = make_policy(executor_factory=spy)
        p = pol.propose(source="test", event=self.trig, evidence=self.ev, candidates=[RULE_MTU])
        res, _ = pol.decide(p["id"], approved=True, approver="alice", post_telemetry=self.post("pass"))
        self.assertEqual(res["status"], "execution_failed")
        self.assertIn("executor error", res["execution"]["detail"])
        self.assertIsNone(res["verification"])

    def test_reproposing_same_event_is_idempotent(self):
        again = self.policy.propose(source="test", event=self.trig, evidence=self.ev, candidates=[RULE_MTU])
        self.assertEqual(again["id"], self.p["id"])
        self.assertTrue(again["deduplicated"])
        other = dict(self.trig, event_id="evt-other")
        dup = self.policy.propose(source="test", event=other, evidence=self.ev, candidates=[RULE_MTU])
        self.assertEqual(dup["id"], self.p["id"])
        self.assertEqual(len(self.policy.list()), 1)

    def test_ansible_proposal_cannot_run_in_simulate_process(self):
        reg_policy = make_policy(mode="ansible", inventory={"gpu-b"}, executor_factory=self.spy)
        p = reg_policy.propose(source="test", event=self.trig, evidence=self.ev, candidates=[RULE_MTU])
        from controller.remediation import RemediationPolicy
        sim = RemediationPolicy(store=reg_policy.store, registry=reg_policy.registry, mode="simulate",
                                executor_factory=self.spy)
        _, code = sim.decide(p["id"], approved=True, approver="alice")
        self.assertEqual(code, 409)
        self.assertEqual(self.spy.calls, [])


class ProcessorBoundaryTests(unittest.TestCase):
    def test_only_the_policy_executor_calls_ansible(self):
        offenders = []
        for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if rel.startswith(("myenv/", "tests/", "frontend/")) or rel in (
                    "controller/ansible_runner.py", "controller/remediation/executors.py"):
                continue
            with open(path, encoding="utf-8", errors="ignore") as fh:
                if "run_playbook" in fh.read():
                    offenders.append(rel)
        self.assertEqual(offenders, [])

    def test_processor_without_dry_run_only_proposes(self):
        from controller.demo_scenarios import load_mtu_two_host
        from controller.processor import Processor

        spy = SpyExecutor()
        policy = make_policy(executor_factory=spy)
        with mock.patch("controller.processor.audit_log"), \
                mock.patch("controller.remediation.executors.run_playbook", side_effect=AssertionError):
            proc = Processor(dry_run=False, policy=policy, enable_ai=False)
            self.assertFalse(hasattr(proc, "attempt_remediation"))
            decisions = [proc.process_event(e) for e in load_mtu_two_host()["telemetry"]]
        rem = decisions[-1]["remediation"]
        self.assertEqual(rem["status"], "pending_approval")
        self.assertEqual(rem["action"], "set_mtu")
        self.assertEqual(decisions[-1]["evidence"]["confidence"]["level"], "high")
        self.assertEqual(spy.calls, [])

    def test_processor_ml_score_cannot_bypass_policy(self):
        from controller.processor import Processor

        policy = make_policy(executor_factory=SpyExecutor())
        with mock.patch("controller.processor.audit_log"):
            proc = Processor(dry_run=True, policy=policy, enable_ai=False)
            proc.model.predict = lambda *_a, **_k: {"priority_score": 0.99, "localization": "node1"}
            dec = proc.process_event(event("node1", dmesg="kernel oops"))
        self.assertEqual(dec["remediation"]["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
