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
from controller.evidence import build_evidence
from controller.remediation import RemediationPolicy, get_policy, summarize
from controller.remediation.candidates import build_candidates
from controller.demo_scenarios import MTU_SCENARIO_ID, POST_CHECK_VARIANTS, load_mtu_two_host

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


def _parse_ts(ts: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


class TriageService:
    """Manages the in-memory telemetry state and coordinates triage execution."""

    def __init__(self, policy: Optional[RemediationPolicy] = None, enable_ai: bool = True):
        self._lock = Lock()
        self._events: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._audit_log: List[Dict[str, Any]] = []
        self._ai_incidents: List[Dict[str, Any]] = []
        self._model_status: Dict[str, Any] = {"trained": False, "message": "Not trained yet"}
        # Change records by scenario/source id; fed to evidence correlation.
        self._changes: Dict[str, List[Dict[str, Any]]] = {}
        # Scripted post-remediation telemetry for demo proposals (proposal id -> samples).
        self._scenario_post: Dict[str, List[Dict[str, Any]]] = {}
        self._demo_variant: Optional[str] = None

        # Lazy-loaded controller components
        self._log_parser: Optional[LogParser] = None
        self._triage_model: Optional[TriageModel] = None
        self._orchestrator = None
        self._orchestrator_failed = not enable_ai
        self._policy = policy

    @property
    def policy(self) -> RemediationPolicy:
        if self._policy is None:
            self._policy = get_policy()
        return self._policy

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

        # 4. Remediation candidate (a request only; the shared policy decides)
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
            playbook = select_playbook(reason, log_class, rule.get("targets") if rule.get("action") == "remediate" else None)

        # 5. Deterministic, topology-aware evidence
        previous, peers = self._context_samples(event)
        evidence = build_evidence(
            event,
            self.policy.registry,
            previous=previous,
            peer_samples=peers,
            changes=[c for chs in self._changes.values() for c in chs],
            rule=rule,
            log_class=log_class,
        )

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
            "simulated": bool(event.get("simulated")),
            "scenario_id": event.get("scenario_id"),
            "evidence": evidence,
        }

        # 6. Optional AI multi-agent workflow (model output is kept separate from evidence)
        ai_result = None
        orchestrator = self.get_orchestrator()
        if orchestrator is not None:
            try:
                base_decision = {
                    "rule": rule,
                    "ml": ml_result,
                    "log_class": log_class,
                }
                ai_result = orchestrator.run(event, base_decision)
                ai_result["scenario_id"] = event.get("scenario_id")
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
                evidence["model_explanation"] = {
                    "label": "model-generated",
                    "backend": rca.get("_backend") or ai_result.get("llm_backend"),
                    "fault_domain": rca.get("fault_domain"),
                    "root_cause": rca.get("root_cause"),
                    "explanation": rca.get("explanation"),
                    "model_reported_confidence": rca.get("confidence"),
                    "note": "Generated by the AI layer; not a deterministic observation.",
                }
            except Exception:
                LOG.exception("AI workflow failed for event %s", event.get("event_id"))
                ai_result = None

        # 7. Shared remediation policy: validate, preview, wait for approval
        candidates = build_candidates(rule, ml_result, log_class, (ai_result or {}).get("remediation"))
        if candidates:
            proposal = self.policy.propose(
                source="api",
                event=event,
                evidence=evidence,
                candidates=candidates,
                incident_ref=(ai_result or {}).get("incident_id") or event.get("event_id"),
                scenario_id=event.get("scenario_id"),
            )
            decision["remediation_id"] = proposal["id"]
            decision["remediation"] = summarize(proposal)
            if ai_result is not None:
                ai_result["remediation_id"] = proposal["id"]
                self._sync_ai_status(ai_result, proposal)
                decision["ai"]["status"] = ai_result["remediation"].get("status")
            self._legacy_audit(proposal, f"proposed: {proposal['status']}")

        if ai_result is not None:
            with self._lock:
                self._ai_incidents.append(ai_result)

        return decision

    # -----------------------------------------------------------------------
    # Remediation helpers
    # -----------------------------------------------------------------------
    def _context_samples(self, event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Previous sample from the same host and the latest sample of every other host."""
        cur = _parse_ts(event.get("ts"))
        previous, latest = None, {}
        with self._lock:
            events = list(self._events)
        for ev in events:
            if ev is event:
                continue
            if ev.get("host") == event.get("host"):
                t = _parse_ts(ev.get("ts"))
                if cur and t and t < cur:
                    previous = ev
            elif ev.get("host"):
                latest[ev["host"]] = ev
        return previous, list(latest.values())

    @staticmethod
    def _sync_ai_status(ai_result: Dict[str, Any], proposal: Dict[str, Any]) -> None:
        """The policy status is authoritative; the AI record mirrors it."""
        rem = ai_result.setdefault("remediation", {})
        rem["ai_proposed_status"] = rem.get("ai_proposed_status", rem.get("status"))
        rem["status"] = proposal["status"]
        rem["policy"] = summarize(proposal)

    def _legacy_audit(self, proposal: Dict[str, Any], status: str) -> None:
        prev = proposal.get("preview") or {}
        entry = {
            "ts": iso_now(),
            "event_id": proposal.get("event_id"),
            "host": proposal.get("host"),
            "playbook": prev.get("playbook"),
            "reason": proposal.get("block_reason") or (proposal.get("diagnosis") or {}).get("statement"),
            "status": status,
            "remediation_id": proposal.get("id"),
            "mode": proposal.get("mode"),
            "scenario_id": proposal.get("scenario_id"),
        }
        with self._lock:
            self._audit_log.append(entry)

    def _post_samples(self, proposal: Dict[str, Any]) -> List[Dict[str, Any]]:
        if proposal["id"] in self._scenario_post:
            return list(self._scenario_post[proposal["id"]])
        hosts = set((proposal.get("preview") or {}).get("limit") or [])
        since = _parse_ts((proposal.get("execution") or {}).get("ts") or (proposal.get("decision") or {}).get("ts"))
        with self._lock:
            events = list(self._events)
        return [e for e in events if e.get("host") in hosts and since and (_parse_ts(e.get("ts")) or since) > since]

    def list_remediations(self, limit: int = 50, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.policy.list(limit=limit, scenario_id=scenario_id)

    def get_remediation(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        p = self.policy.get(proposal_id)
        if p is not None:
            p["audit"] = self.policy.audit(limit=200, proposal_id=proposal_id)
        return p

    def get_remediation_audit(self, limit: int = 100, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.policy.audit(limit=limit, scenario_id=scenario_id)

    def decide_remediation(self, proposal_id: str, approved: bool, approver: str,
                           preview_digest: Optional[str] = None,
                           reason: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        res, code = self.policy.decide(proposal_id, approved=approved, approver=approver,
                                       preview_digest=preview_digest, reason=reason,
                                       post_telemetry=self._post_samples)
        if code == 200:
            self._legacy_audit(res, self._status_text(res))
            self._refresh_ai(res)
        return res, code

    def verify_remediation(self, proposal_id: str) -> Tuple[Dict[str, Any], int]:
        p = self.policy.get(proposal_id)
        if p is None:
            return {"error": "proposal not found"}, 404
        res, code = self.policy.verify(proposal_id, self._post_samples(p))
        if code == 200:
            self._legacy_audit(res, self._status_text(res))
            self._refresh_ai(res)
        return res, code

    @staticmethod
    def _status_text(p: Dict[str, Any]) -> str:
        ex = p.get("execution") or {}
        if not ex:
            return p["status"]
        return f"{p['status']} ({'simulated' if ex.get('simulated') else 'executed'})"

    def _refresh_ai(self, proposal: Dict[str, Any]) -> None:
        with self._lock:
            for r in self._ai_incidents:
                if r.get("remediation_id") == proposal["id"]:
                    self._sync_ai_status(r, proposal)
                    r["validation"] = self._validation_view(proposal, r.get("validation"))

    @staticmethod
    def _validation_view(proposal: Dict[str, Any], model_view: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        ver = proposal.get("verification")
        if not ver:
            return model_view or {}
        outcome = ver["outcome"]
        if model_view and model_view.get("authoritative"):
            model_view = model_view.get("model_assessment")
        return {
            "resolved": True if outcome == "passed" else (False if outcome == "failed" else None),
            "outcome": outcome,
            "authoritative": "deterministic_post_check",
            "checks": ver.get("checks"),
            "residual_risk": None if outcome == "passed" else ver.get("summary"),
            "recommendation": ver.get("summary"),
            "model_assessment": model_view or None,
        }

    # -----------------------------------------------------------------------
    # Deterministic demo
    # -----------------------------------------------------------------------
    def reset_demo(self, scenario_id: str = MTU_SCENARIO_ID) -> Dict[str, Any]:
        """Remove only data that belongs to ``scenario_id``."""
        with self._lock:
            before = len(self._events) + len(self._decisions) + len(self._ai_incidents) + len(self._audit_log)
            self._events = [e for e in self._events if e.get("scenario_id") != scenario_id]
            self._decisions = [d for d in self._decisions if d.get("scenario_id") != scenario_id]
            self._ai_incidents = [r for r in self._ai_incidents if r.get("scenario_id") != scenario_id]
            self._audit_log = [a for a in self._audit_log if a.get("scenario_id") != scenario_id]
            removed = before - (len(self._events) + len(self._decisions) + len(self._ai_incidents)
                                + len(self._audit_log))
            self._changes.pop(scenario_id, None)
            for pid in [k for k, v in self._scenario_post.items() if v and v[0].get("scenario_id") == scenario_id]:
                del self._scenario_post[pid]
            self._demo_variant = None
        proposals = self.policy.reset_scenario(scenario_id)
        return {"ok": True, "scenario_id": scenario_id, "removed_records": removed, "removed_proposals": proposals}

    def run_demo(self, variant: str = "pass") -> Tuple[Dict[str, Any], int]:
        if variant not in POST_CHECK_VARIANTS:
            return {"error": f"variant must be one of {list(POST_CHECK_VARIANTS)}"}, 400
        sc = load_mtu_two_host()
        self.reset_demo(sc["scenario_id"])
        with self._lock:
            self._changes[sc["scenario_id"]] = sc["changes"]
            self._demo_variant = variant
        trigger = None
        for ev in sc["telemetry"]:
            dec = self.process_single(ev)
            if ev.get("role") == "trigger":
                trigger = dec
        rid = (trigger or {}).get("remediation_id")
        if rid:
            with self._lock:
                self._scenario_post[rid] = sc["post_checks"][variant]
        return self.get_demo(), 200

    def get_demo(self) -> Dict[str, Any]:
        sc = load_mtu_two_host()
        sid = sc["scenario_id"]
        with self._lock:
            events = [e for e in self._events if e.get("scenario_id") == sid]
            decisions = [d for d in self._decisions if d.get("scenario_id") == sid]
            variant = self._demo_variant
        trigger_id = next(e["event_id"] for e in sc["telemetry"] if e.get("role") == "trigger")
        trigger = next((d for d in decisions if d.get("event_id") == trigger_id), None)
        proposal = self.get_remediation(trigger["remediation_id"]) if trigger and trigger.get("remediation_id") else None
        if trigger and proposal:
            trigger = {**trigger, "remediation": summarize(proposal)}
        return {
            "scenario_id": sid,
            "title": sc["title"],
            "simulated": True,
            "disclaimer": sc["disclaimer"],
            "story": sc["story"],
            "scenario_clock": sc["scenario_clock"],
            "loaded": bool(events),
            "post_check_variant": variant,
            "variants": list(POST_CHECK_VARIANTS),
            "topology": self.policy.registry.view(sc["topology_id"]),
            "changes": sc["changes"],
            "events": events,
            "decision": trigger,
            "proposal": proposal,
            "audit": self.policy.audit(limit=200, scenario_id=sid) if events else [],
        }

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
            recent = self._decisions[-limit:]
        out = []
        for d in recent:
            rid = d.get("remediation_id")
            out.append({**d, "remediation": summarize(self.policy.get(rid))} if rid else d)
        return out

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
                "remediation_id": r.get("remediation_id"),
                "simulated": bool((r.get("event") or {}).get("simulated")),
            })
        return out

    def get_ai_incident_detail(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for r in reversed(self._ai_incidents):
                if r.get("incident_id") == incident_id:
                    return r
        return None

    def approve_ai_incident(self, incident_id: str, approved: bool, approver: str = "api-user",
                            preview_digest: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
        """Legacy AI approval endpoint; delegates to the shared remediation policy."""
        with self._lock:
            target = next(
                (r for r in reversed(self._ai_incidents) if r.get("incident_id") == incident_id),
                None,
            )
        if target is None:
            return {"error": "incident not found"}, 404
        rid = target.get("remediation_id")
        if not rid:
            return {"error": "no remediation proposal exists for this incident"}, 409

        proposal, code = self.decide_remediation(rid, approved, approver, preview_digest=preview_digest)
        if code != 200:
            return {"error": proposal.get("error", "decision refused"), "status": (proposal.get("proposal") or {}).get("status")}, code

        orchestrator = self.get_orchestrator()
        if approved and orchestrator is not None:
            try:
                samples = self._post_samples(proposal)
                result = orchestrator.resume_after_approval(target, samples[-1] if samples else None)
                result["remediation_id"] = rid
                result["scenario_id"] = target.get("scenario_id")
                self._sync_ai_status(result, proposal)
                result["validation"] = self._validation_view(proposal, result.get("validation"))
                with self._lock:
                    self._ai_incidents.append(result)
            except Exception:
                LOG.exception("resume_after_approval failed for %s", incident_id)

        return {
            "ok": True,
            "status": proposal["status"],
            "incident_id": incident_id,
            "remediation_id": rid,
            "validation": self._validation_view(proposal, None),
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

    def process_single(self, event: Dict[str, Any], external: bool = False) -> Dict[str, Any]:
        if external:
            # Scenario membership is assigned by the demo runner, never by API clients.
            event.pop("scenario_id", None)
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
            self._changes.clear()
            self._scenario_post.clear()
            self._demo_variant = None
        # Persisted remediation proposals and their audit trail are intentionally kept.
        return {"ok": True}


# Global singleton instance for the service layer
service = TriageService()
