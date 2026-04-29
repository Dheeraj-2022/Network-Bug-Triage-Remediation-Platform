#!/usr/bin/env python3
"""
Network Bug Triage & Remediation Platform - Web UI

Flask application that provides:
  - Dashboard with live event feed
  - Inject synthetic events and view triage results
  - View remediation audit log
  - Trigger model training
  - View system status

Usage:
    python app.py
"""

import json
import logging
import os
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify, render_template, request

# Ensure project root is on path
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from controller.rules_engine import rule_based_triage
from controller.nlp_parser import LogParser
from controller.triage_model import TriageModel

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "nbt-platform-secret"

LOG = logging.getLogger("nbt.webapp")
LOG.setLevel(logging.INFO)
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
LOG.addHandler(_h)

# ---------------------------------------------------------------------------
# Shared state (in-memory for demo)
# ---------------------------------------------------------------------------
_lock = Lock()
_events: list = []          # raw telemetry events
_decisions: list = []       # triage decisions
_audit_log: list = []       # remediation audit entries
_model_status: dict = {"trained": False, "message": "Not trained yet"}

from typing import Optional

# ---------------------------------------------------------------------------
# Lazy-loaded components
# ---------------------------------------------------------------------------
_log_parser: Optional[LogParser] = None
_triage_model: Optional[TriageModel] = None


def _get_log_parser() -> LogParser:
    global _log_parser
    if _log_parser is None:
        _log_parser = LogParser()
    return _log_parser


def _get_triage_model() -> TriageModel:
    global _triage_model
    if _triage_model is None:
        _triage_model = TriageModel()
    return _triage_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SAMPLE_EVENTS_PATH = os.path.join(ROOT, "data", "sample_events.json")
AUDIT_LOG_PATH = os.path.join(ROOT, "logs", "remediation_audit.log")
MODEL_PATH = os.path.join(ROOT, "controller", "models", "xgb_model.joblib")


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def _make_synthetic_event(host: str, inject_error: bool = False):
    ifaces = {
        "eth0": {
            "rx_bytes": random.randint(1000, 1_000_000),
            "tx_bytes": random.randint(1000, 1_000_000),
            "errin": 0, "errout": 0, "mtu": 1500,
        }
    }
    rdma = {"qp_errors": 0, "rq_errors": 0, "srq_errors": 0}
    dmesg = "Normal boot messages"

    if inject_error:
        fault = random.choice(["mtu", "iface_err", "rdma", "driver"])
        if fault == "iface_err":
            ifaces["eth0"]["errout"] = random.randint(6, 20)
            dmesg = "eth0: TX errors detected; driver reports packet drop"
        elif fault == "mtu":
            ifaces["eth0"]["mtu"] = random.choice([1400, 9000])
            dmesg = "eth0: MTU mismatch detected"
        elif fault == "rdma":
            rdma["qp_errors"] = random.randint(1, 5)
            dmesg = "mlx5_core: RDMA QP reset or qp error"
        elif fault == "driver":
            dmesg = "driver: kernel oops - stack trace ..."

    return {
        "event_id": f"evt-{host}-{int(time.time())}-{random.randint(1, 9999)}",
        "host": host,
        "ts": iso_now(),
        "ifaces": ifaces,
        "rdma": rdma,
        "dmesg_tail": dmesg,
        "sample_packets": [{"src": "10.0.0.1", "dst": "10.0.0.2", "len": 128, "proto": "TCP"}],
    }


def _process_event(event: dict) -> dict:
    """Run full triage pipeline on a single event and return decision dict."""
    # Rule-based
    rule = rule_based_triage(event)

    # NLP
    parser = _get_log_parser()
    dmesg = event.get("dmesg_tail", "")
    embedding = parser.embed_logs(dmesg)
    log_class = parser.classify_logs(dmesg)

    # ML
    model = _get_triage_model()
    ml_result = model.predict(event, embedding)

    # Remediation decision
    should_remediate = False
    playbook = None
    reason = ""
    if rule.get("action") == "remediate":
        should_remediate = True
        reason = rule.get("reason", "")
    elif ml_result.get("priority_score", 0) >= 0.85:
        should_remediate = True
        reason = f"ML-priority:{ml_result.get('priority_score')}"

    if should_remediate:
        if "mtu" in reason.lower() or log_class == "MTU_MISMATCH":
            playbook = "remediate_mtu.yml"
        elif log_class == "DRIVER_FAULT":
            playbook = "restart_driver.yml"
        else:
            playbook = "remediate_mtu.yml"

    decision = {
        "ts": iso_now(),
        "host": event.get("host"),
        "event_id": event.get("event_id"),
        "rule_action": rule.get("action"),
        "rule_reason": rule.get("reason"),
        "log_class": log_class,
        "ml_priority": round(ml_result.get("priority_score", 0), 4),
        "ml_localization": ml_result.get("localization"),
        "remediate": should_remediate,
        "playbook": playbook,
    }

    # Record audit
    if should_remediate:
        audit_entry = {
            "ts": iso_now(),
            "event_id": event.get("event_id"),
            "host": event.get("host"),
            "playbook": playbook,
            "reason": reason,
            "status": "dry-run (UI mode)",
        }
        with _lock:
            _audit_log.append(audit_entry)

    return decision


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({
            "total_events": len(_events),
            "total_decisions": len(_decisions),
            "remediations": sum(1 for d in _decisions if d.get("remediate")),
            "model_trained": os.path.exists(MODEL_PATH),
            "model_status": _model_status,
        })


@app.route("/api/events")
def api_events():
    with _lock:
        return jsonify(_events[-50:])


@app.route("/api/decisions")
def api_decisions():
    with _lock:
        return jsonify(_decisions[-50:])


@app.route("/api/audit")
def api_audit():
    with _lock:
        return jsonify(_audit_log[-50:])


@app.route("/api/inject", methods=["POST"])
def api_inject():
    """Inject synthetic events and process them through the triage pipeline."""
    body = request.get_json(silent=True) or {}
    count = int(body.get("count", 3))
    inject_errors = body.get("inject_errors", True)
    hosts = ["node1", "node2", "node3", "node4", "node5"]

    results = []
    for i in range(count):
        host = random.choice(hosts)
        ev = _make_synthetic_event(host, inject_error=(inject_errors and i % 2 == 0))
        decision = _process_event(ev)
        with _lock:
            _events.append(ev)
            _decisions.append(decision)
        results.append(decision)

    return jsonify({"injected": count, "decisions": results})


@app.route("/api/process", methods=["POST"])
def api_process_single():
    """Process a single custom event."""
    event = request.get_json(silent=True)
    if not event:
        return jsonify({"error": "provide a JSON event body"}), 400
    if "event_id" not in event:
        event["event_id"] = f"custom-{int(time.time())}-{random.randint(1,9999)}"
    if "host" not in event:
        event["host"] = "custom-host"
    if "ts" not in event:
        event["ts"] = iso_now()
    if "ifaces" not in event:
        event["ifaces"] = {}
    if "rdma" not in event:
        event["rdma"] = {}
    if "dmesg_tail" not in event:
        event["dmesg_tail"] = ""

    decision = _process_event(event)
    with _lock:
        _events.append(event)
        _decisions.append(decision)
    return jsonify(decision)


@app.route("/api/load_sample_events", methods=["POST"])
def api_load_samples():
    """Load events from data/sample_events.json and triage them."""
    if not os.path.exists(SAMPLE_EVENTS_PATH):
        return jsonify({"error": "sample_events.json not found"}), 404
    with open(SAMPLE_EVENTS_PATH) as f:
        events = json.load(f)
    # Take a subset to keep things fast
    subset = events[:20]
    results = []
    for ev in subset:
        if "event_id" not in ev:
            ev["event_id"] = f"sample-{int(time.time())}-{random.randint(1,9999)}"
        if "ts" not in ev:
            ev["ts"] = iso_now()
        decision = _process_event(ev)
        with _lock:
            _events.append(ev)
            _decisions.append(decision)
        results.append(decision)
    return jsonify({"loaded": len(subset), "decisions": results})


@app.route("/api/train", methods=["POST"])
def api_train():
    """Trigger model training (synchronous, may take a moment)."""
    global _model_status, _triage_model
    try:
        _model_status = {"trained": False, "message": "Training in progress..."}
        # Run training inline
        from controller.model.triage_model_training import train_model
        report = train_model()
        _model_status = {"trained": True, "message": f"Training complete. {report}"}
        # Reload model
        _triage_model = None  # force reload on next use
        return jsonify({"ok": True, "message": _model_status["message"]})
    except Exception as e:
        _model_status = {"trained": False, "message": f"Training failed: {e}"}
        LOG.exception("Training failed")
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Clear all in-memory state."""
    with _lock:
        _events.clear()
        _decisions.clear()
        _audit_log.clear()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "controller", "models"), exist_ok=True)
    print("=" * 60)
    print("  Network Bug Triage & Remediation Platform")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)
