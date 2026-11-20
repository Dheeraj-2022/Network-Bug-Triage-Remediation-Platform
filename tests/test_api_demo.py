#!/usr/bin/env python3
"""
FastAPI contract + end-to-end demo tests (TestClient, in-memory store, AI off).

Run:  python -m unittest tests.test_api_demo -v
"""

import os
import unittest

from tests.support import make_policy

from fastapi.testclient import TestClient

import main
from api.service import service

DEMO = "/api/demo/mtu-two-host"


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        os.environ.pop("NBT_API_KEY", None)
        service.clear()
        service._policy = make_policy()
        service._orchestrator_failed = True
        service._orchestrator = None
        self.client = TestClient(main.app)

    def load(self, variant="pass"):
        r = self.client.post(f"{DEMO}/load", json={"post_check": variant})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def decide(self, demo, approved=True, approver="alice", digest=None):
        p = demo["proposal"]
        return self.client.post(f"/api/remediations/{p['id']}/decision", json={
            "approved": approved, "approver": approver, "preview_digest": digest or p["preview_digest"]})


class DemoEndToEndTests(ApiTestCase):
    def test_demo_end_to_end_success(self):
        demo = self.load("pass")
        self.assertTrue(demo["simulated"])
        self.assertEqual(len(demo["events"]), 3)
        ev = demo["decision"]["evidence"]
        self.assertEqual(ev["inference"]["fault_domain"], "MTU_MISMATCH")
        self.assertEqual(ev["mtu_checks"][0]["expected"], 9000)
        self.assertEqual(ev["mtu_checks"][0]["observed"], 1500)
        self.assertEqual(ev["localization"]["status"], "resolved")
        self.assertEqual(ev["localization"]["paths"][0]["id"], "path:gpu-a--gpu-b")
        self.assertIn("switch:leaf-1", [b["entity_id"] for b in ev["scope"]["blast_radius"]])
        self.assertTrue(any(ln["text"].startswith("[sim]") for ln in ev["log_lines"]))
        self.assertEqual(demo["proposal"]["status"], "pending_approval")
        self.assertEqual(demo["topology"]["topology_id"], "demo-mtu-two-host")

        r = self.decide(demo)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "resolved")
        state = self.client.get(DEMO).json()
        kinds = [a["kind"] for a in state["audit"]]
        self.assertEqual(kinds, ["recommended", "previewed", "approved", "simulated", "post_check"])
        self.assertEqual(state["decision"]["remediation"]["status"], "resolved")

        self.assertEqual(self.decide(demo).status_code, 409)

    def test_demo_failure_variants_are_not_resolved(self):
        for variant, status in (("fail", "verification_failed"), ("inconclusive", "verification_inconclusive")):
            with self.subTest(variant=variant):
                r = self.decide(self.load(variant))
                self.assertEqual(r.json()["status"], status)

    def test_rejection(self):
        r = self.decide(self.load(), approved=False)
        self.assertEqual(r.json()["status"], "rejected")
        self.assertIsNone(r.json()["execution"])

    def test_demo_is_repeatable_and_scoped(self):
        self.client.post("/api/process", json={"event_id": "user-evt-1", "host": "node1"})
        first = self.load()
        self.decide(first)
        second = self.load()
        self.assertEqual(first["proposal"]["id"], second["proposal"]["id"])
        self.assertEqual(second["proposal"]["status"], "pending_approval")
        self.assertEqual([e["event_id"] for e in first["events"]], [e["event_id"] for e in second["events"]])
        self.assertEqual(len(second["audit"]), 2)
        events = self.client.get("/api/events").json()
        self.assertEqual(sum(e["event_id"] == "user-evt-1" for e in events), 1)
        self.assertEqual(len(events), 4)
        self.assertEqual(len(self.client.get("/api/remediations?scenario_id=demo:mtu-two-host").json()), 1)

        self.client.post(f"{DEMO}/reset")
        self.assertFalse(self.client.get(DEMO).json()["loaded"])
        self.assertEqual(len(self.client.get("/api/events").json()), 1)

    def test_stale_digest_and_bad_inputs(self):
        demo = self.load()
        self.assertEqual(self.decide(demo, digest="0000").status_code, 409)
        self.assertEqual(self.decide(demo, approver="").status_code, 422)
        self.assertEqual(self.client.post("/api/remediations/not-an-id/decision",
                                          json={"approved": True, "approver": "a"}).status_code, 422)
        self.assertEqual(self.client.post(f"{DEMO}/load", json={"post_check": "maybe"}).status_code, 422)
        self.assertEqual(self.client.post("/api/process", json={"host": "bad host;rm"}).status_code, 422)

    def test_clients_cannot_inject_into_demo_scope(self):
        self.client.post("/api/process", json={"event_id": "x", "host": "node1", "scenario_id": "demo:mtu-two-host"})
        self.client.post(f"{DEMO}/reset")
        self.assertEqual(len(self.client.get("/api/events").json()), 1)


class LegacyContractTests(ApiTestCase):
    def test_existing_endpoints_still_respond(self):
        self.assertEqual(set(self.client.get("/api/status").json()) >= {
            "total_events", "total_decisions", "remediations", "model_trained", "ai_incidents"}, True)
        inj = self.client.post("/api/inject", json={"count": 2, "inject_errors": True}).json()
        self.assertEqual(inj["injected"], 2)
        for d in self.client.get("/api/decisions").json():
            self.assertIn("evidence", d)
            self.assertIn("remediate", d)
        self.assertEqual(self.client.get("/api/audit").status_code, 200)
        self.assertEqual(self.client.get("/api/ai/incidents").json(), [])
        self.assertEqual(self.client.post("/api/ai/approve", json={"incident_id": "nope"}).status_code, 404)
        self.assertEqual(self.client.post("/api/clear").json(), {"ok": True})

    def test_api_key_when_configured(self):
        os.environ["NBT_API_KEY"] = "test-secret"
        try:
            info = self.client.get("/api/auth").json()
            self.assertTrue(info["api_key_required"])
            self.assertNotIn("test-secret", str(info))
            self.assertEqual(self.client.get("/api/status").status_code, 401)
            self.assertEqual(self.client.post(f"{DEMO}/load", headers={"X-API-Key": "wrong"}).status_code, 401)
            self.assertEqual(self.client.get("/api/status", headers={"X-API-Key": "test-secret"}).status_code, 200)
        finally:
            os.environ.pop("NBT_API_KEY", None)
        self.assertFalse(self.client.get("/api/auth").json()["api_key_required"])


class AiApprovalPathTests(ApiTestCase):
    """The legacy /api/ai/approve endpoint must go through the same policy."""

    def setUp(self):
        super().setUp()
        from controller.ai.config import AIConfig
        from controller.ai.orchestrator import Orchestrator

        cfg = AIConfig.load()
        cfg.enabled = True
        cfg.vertex.enabled = False
        cfg.memory.enabled = False
        service._orchestrator = Orchestrator(cfg)
        service._orchestrator_failed = False

    def test_ai_approval_uses_shared_policy(self):
        demo = self.load("fail")
        ai_id = demo["decision"]["ai"]["incident_id"]
        self.assertEqual(demo["decision"]["ai"]["status"], "pending_approval")
        self.assertEqual(demo["decision"]["remediation_id"], demo["proposal"]["id"])
        self.assertEqual(demo["decision"]["evidence"]["model_explanation"]["label"], "model-generated")
        self.assertIn("ai", demo["proposal"]["recommenders"])

        r = self.client.post("/api/ai/approve", json={"incident_id": ai_id, "approved": True, "approver": "carol"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "verification_failed")
        self.assertFalse(r.json()["validation"]["resolved"])
        self.assertEqual(self.client.post("/api/ai/approve", json={"incident_id": ai_id}).status_code, 409)
        detail = self.client.get(f"/api/ai/incident/{ai_id}").json()
        self.assertEqual(detail["validation"]["authoritative"], "deterministic_post_check")


if __name__ == "__main__":
    unittest.main()
