"""
Service layer coordinating the triage and remediation pipeline.

Reuses existing controller modules:
- controller.rules_engine: rule_based_triage, select_playbook
- controller.nlp_parser: LogParser
- controller.triage_model: TriageModel
- controller.ai: orchestrator & multi-agent reasoning
- controller.model.triage_model_training: train_model
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
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from controller.rules_engine import rule_based_triage, select_playbook
from controller.nlp_parser import LogParser
from controller.triage_model import TriageModel

try:
    from controller.ai import get_orchestrator, get_ai_config
except Exception:
    get_orchestrator = None
    get_ai_config = None

LOG = logging.getLogger("nbt.service")
LOG.setLevel(logging.INFO)

SAMPLE_EVENTS_PATH = os.path.join(ROOT, "data", "sample_events.json")
MODEL_PATH = os.path.join(ROOT, "controller", "models", "xgb_model.joblib")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TriageService:
    """Manages the in-memory telemetry state and coordinates triage execution."""

    def __init__(self):
        self._lock = Lock()
        self._events: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._audit_log: List[Dict[str, Any]] = []
        self._ai_incidents: List[Dict[str, Any]] = []
        self._model_status: Dict[str, Any] = {"trained": False, "message": "Not trained yet"}

        # Lazy-loaded controller components
        self._log_parser: Optional[LogParser] = None
        self._triage_model: Optional[TriageModel] = None
        self._orchestrator = None
        self._orchestrator_failed = False

    def get_log_parser(self) -> LogParser:
        if self._log_parser is None:
            self._log_parser = LogParser()
        return self._log_parser

    def get_triage_model(self) -> TriageModel:
        if self._triage_model is None:
            self._triage_model = TriageModel()
        return self._triage_model

    def get_orchestrator(self):
        """Lazily load the AI orchestrator or gracefully degrade if disabled."""
        if self._orchestrator_failed or get_orchestrator is None:
            return None
        if self._orchestrator is None:
            try:
                cfg = get_ai_config() if get_ai_config else None
                if cfg is not None and not cfg.enabled:
                    self._orchestrator_failed = True
                    return None
                self._orchestrator = get_orchestrator()
            except Exception:
                LOG.exception("Failed to initialize AI orchestrator; disabling AI layer")
                self._orchestrator_failed = True
                return None
        return self._orchestrator

    def make_synthetic_event(self, host: str, inject_error: bool = False) -> Dict[str, Any]:
        """Generate a simulated host telemetry event."""
        ifaces = {
            "eth0": {
                "rx_bytes": random.randint(1000, 1_000_000),
                "tx_bytes": random.randint(1000, 1_000_000),
                "errin": 0,
                "errout": 0,
                "mtu": 1500,
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

    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Run full triage pipeline on a single event using controller modules."""
        # 1. Rule-based evaluation
        rule = rule_based_triage(event)

        # 2. NLP log parsing & classification
        parser = self.get_log_parser()
        dmesg = event.get("dmesg_tail", "")
        embedding = parser.embed_logs(dmesg)
        log_class = parser.classify_logs(dmesg)

        # 3. ML triage model prediction
        model = self.get_triage_model()
        ml_result = model.predict(event, embedding)

        # 4. Remediation policy decision
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
            playbook = select_playbook(reason, log_class)

        decision: Dict[str, Any] = {
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

        # 5. Optional AI multi-agent workflow
        orchestrator = self.get_orchestrator()
        if orchestrator is not None:
            try:
                base_decision = {
                    "rule": rule,
                    "ml": ml_result,
                    "log_class": log_class,
                }
                ai_result = orchestrator.run(event, base_decision)
                rca = ai_result.get("rca", {})
                remediation = ai_result.get("remediation", {})
                decision["ai"] = {
                    "incident_id": ai_result.get("incident_id"),
                    "llm_backend": ai_result.get("llm_backend"),
                    "fault_domain": rca.get("fault_domain"),
                    "root_cause": rca.get("root_cause"),
                    "confidence": rca.get("confidence"),
                    "ai_playbook": remediation.get("playbook"),
                    "risk": remediation.get("risk"),
                    "status": remediation.get("status"),
                    "context_sources": ai_result.get("context_sources", []),
                }
                with self._lock:
                    self._ai_incidents.append(ai_result)
            except Exception:
                LOG.exception("AI workflow failed for event %s", event.get("event_id"))

        # 6. Audit logging for remediation triggers
        if should_remediate:
            audit_entry = {
                "ts": iso_now(),
                "event_id": event.get("event_id"),
                "host": event.get("host"),
                "playbook": playbook,
                "reason": reason,
                "status": "dry-run (UI mode)",
            }
            with self._lock:
                self._audit_log.append(audit_entry)

        return decision

    # -----------------------------------------------------------------------
    # API queries and actions
    # -----------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_decisions": len(self._decisions),
                "remediations": sum(1 for d in self._decisions if d.get("remediate")),
                "model_trained": os.path.exists(MODEL_PATH),
                "model_status": self._model_status,
                "ai_incidents": len(self._ai_incidents),
            }

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return self._events[-limit:]

    def get_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return self._decisions[-limit:]

    def get_audit(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return self._audit_log[-limit:]

    def get_ai_status(self) -> Tuple[Dict[str, Any], int]:
        orchestrator = self.get_orchestrator()
        if orchestrator is None:
            return {"enabled": False, "reason": "AI layer unavailable/disabled"}, 200
        try:
            return orchestrator.status(), 200
        except Exception as e:
            LOG.exception("AI status failed")
            return {"enabled": False, "error": str(e)}, 500

    def get_ai_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._ai_incidents[-limit:]
        out = []
        for r in recent:
            rca = r.get("rca", {})
            rem = r.get("remediation", {})
            out.append({
                "incident_id": r.get("incident_id"),
                "ts": r.get("ts"),
                "host": r.get("host"),
                "event_id": r.get("event_id"),
                "llm_backend": r.get("llm_backend"),
                "fault_domain": rca.get("fault_domain"),
                "root_cause": rca.get("root_cause"),
                "confidence": rca.get("confidence"),
                "explanation": rca.get("explanation"),
                "playbook": rem.get("playbook"),
                "risk": rem.get("risk"),
                "status": rem.get("status"),
                "requires_human_approval": rem.get("requires_human_approval"),
                "context_sources": r.get("context_sources", []),
            })
        return out

    def get_ai_incident_detail(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for r in reversed(self._ai_incidents):
                if r.get("incident_id") == incident_id:
                    return r
        return None

    def approve_ai_incident(self, incident_id: str, approved: bool) -> Tuple[Dict[str, Any], int]:
        orchestrator = self.get_orchestrator()
        with self._lock:
            target = next(
                (r for r in reversed(self._ai_incidents) if r.get("incident_id") == incident_id),
                None,
            )
        if target is None:
            return {"error": "incident not found"}, 404

        if not approved:
            target.get("remediation", {})["status"] = "rejected"
            return {"ok": True, "status": "rejected", "incident_id": incident_id}, 200

        target.get("remediation", {})["status"] = "approved"
        result = target
        if orchestrator is not None:
            try:
                result = orchestrator.resume_after_approval(target)
                with self._lock:
                    self._ai_incidents.append(result)
            except Exception:
                LOG.exception("resume_after_approval failed")

        return {
            "ok": True,
            "status": "approved",
            "incident_id": incident_id,
            "validation": result.get("validation", {}),
        }, 200

    def inject_events(self, count: int = 3, inject_errors: bool = True) -> Dict[str, Any]:
        count = max(1, min(count, 100))
        hosts = ["node1", "node2", "node3", "node4", "node5"]
        results = []

        for i in range(count):
            host = random.choice(hosts)
            ev = self.make_synthetic_event(host, inject_error=(inject_errors and i % 2 == 0))
            decision = self.process_event(ev)
            with self._lock:
                self._events.append(ev)
                self._decisions.append(decision)
            results.append(decision)

        return {"injected": count, "decisions": results}

    def process_single(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if "event_id" not in event or not event["event_id"]:
            event["event_id"] = f"custom-{int(time.time())}-{random.randint(1, 9999)}"
        if "host" not in event or not event["host"]:
            event["host"] = "custom-host"
        if "ts" not in event or not event["ts"]:
            event["ts"] = iso_now()
        if "ifaces" not in event or event["ifaces"] is None:
            event["ifaces"] = {}
        if "rdma" not in event or event["rdma"] is None:
            event["rdma"] = {}
        if "dmesg_tail" not in event or event["dmesg_tail"] is None:
            event["dmesg_tail"] = ""

        decision = self.process_event(event)
        with self._lock:
            self._events.append(event)
            self._decisions.append(decision)
        return decision

    def load_sample_events(self) -> Tuple[Dict[str, Any], int]:
        if not os.path.exists(SAMPLE_EVENTS_PATH):
            return {"error": "sample_events.json not found"}, 404

        try:
            with open(SAMPLE_EVENTS_PATH, encoding="utf-8") as f:
                events = json.load(f)
        except (OSError, ValueError) as e:
            LOG.exception("Failed to read sample events")
            return {"error": f"could not read sample_events.json: {e}"}, 500

        if not isinstance(events, list):
            return {"error": "sample_events.json must contain a JSON array"}, 400

        subset = events[:20]
        results = []
        for ev in subset:
            if not isinstance(ev, dict):
                continue
            if "event_id" not in ev:
                ev["event_id"] = f"sample-{int(time.time())}-{random.randint(1, 9999)}"
            if "ts" not in ev:
                ev["ts"] = iso_now()
            decision = self.process_event(ev)
            with self._lock:
                self._events.append(ev)
                self._decisions.append(decision)
            results.append(decision)

        return {"loaded": len(results), "decisions": results}, 200

    def train_model(self) -> Tuple[Dict[str, Any], int]:
        try:
            self._model_status = {"trained": False, "message": "Training in progress..."}
            from controller.model.triage_model_training import train_model

            report = train_model()
            self._model_status = {"trained": True, "message": f"Training complete. {report}"}
            self._triage_model = None  # Force reload on next prediction
            return {"ok": True, "message": self._model_status["message"]}, 200
        except Exception as e:
            self._model_status = {"trained": False, "message": f"Training failed: {e}"}
            LOG.exception("Training failed")
            return {
                "ok": False,
                "error": str(e),
                "trace": traceback.format_exc(),
            }, 500

    def clear(self) -> Dict[str, Any]:
        with self._lock:
            self._events.clear()
            self._decisions.clear()
            self._audit_log.clear()
            self._ai_incidents.clear()
        return {"ok": True}


# Global singleton instance for the service layer
service = TriageService()
