#!/usr/bin/env python3
"""
End-to-end smoke check of the FastAPI app with whatever models are trained in
controller/models (no test overrides). Uses a temporary remediation DB.

    python -m tests.smoke_e2e
"""

import os
import sys
import tempfile

os.environ.setdefault("NBT_DISABLE_EMBEDDINGS", "1")
os.environ["NBT_REMEDIATION_DB"] = os.path.join(tempfile.mkdtemp(), "smoke.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def check(label, resp, expect=200):
    ok = resp.status_code == expect
    print(f"[{'OK' if ok else 'FAIL'}] {label}: HTTP {resp.status_code}")
    if not ok:
        print("   ", resp.text[:300])
    return ok


def run() -> int:
    c = TestClient(main.app)
    results = [check("GET /api/status", c.get("/api/status")), check("GET /api/auth", c.get("/api/auth"))]
    models = c.get("/api/models").json()
    for name, info in models.items():
        print(f"     model {name}: {info['runtime_status']}")
    results.append(check("POST /api/load_sample_events", c.post("/api/load_sample_events")))
    inj = c.post("/api/inject", json={"count": 6, "inject_errors": True})
    results.append(check("POST /api/inject", inj))
    for d in inj.json().get("decisions", []):
        la = d.get("log_anomaly") or {}
        print(f"     {d['host']}: ml={d['ml_priority']} ({d.get('ml_model')}) log_anomaly={la.get('max_score')} "
              f"remediation={(d.get('remediation') or {}).get('status')}")
    demo = c.post("/api/demo/mtu-two-host/load", json={"post_check": "pass"})
    results.append(check("POST /api/demo/mtu-two-host/load", demo))
    p = demo.json()["proposal"]
    dec = c.post(f"/api/remediations/{p['id']}/decision",
                 json={"approved": True, "approver": "smoke", "preview_digest": p["preview_digest"]})
    results.append(check("POST decision (demo)", dec))
    print(f"     demo outcome: {dec.json().get('status')}")
    results.append(dec.json().get("status") == "resolved")
    results.append(check("GET /api/ai/status", c.get("/api/ai/status")))
    results.append(check("GET /api/decisions", c.get("/api/decisions")))
    results.append(check("GET /api/remediations/audit", c.get("/api/remediations/audit")))
    passed = sum(bool(r) for r in results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())
