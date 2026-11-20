"""
The single remediation policy and execution boundary.

Every remediation path — rules, ML, AI, the FastAPI service and the Kafka
processor — must go through :class:`RemediationPolicy`:

1. ``propose``  validates candidates (allowlist, fault-domain applicability,
   targets resolved in the approved topology/inventory, safe variables) and
   stores a preview. Nothing runs at this point.
2. ``decide``   records a human decision (idempotent; stale, duplicate and
   changed-preview decisions are refused). Only an approval executes, using
   the mode bound at preview time (``simulate`` unless explicitly configured).
3. ``verify``   runs the deterministic post-check; only a passing post-check
   marks the incident ``resolved``.

Every step is written to the audit trail.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shlex
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from controller.remediation.catalog import (
    DRIVER_ALLOWLIST,
    action_for,
    inventory_hosts,
    valid_approver,
    valid_host,
    valid_iface,
    valid_mtu,
)
from controller.remediation.executors import executor_for
from controller.remediation.store import ProposalStore, iso_now
from controller.remediation.verification import verify as run_post_check
from controller.topology import TopologyRegistry, get_registry

LOG = logging.getLogger("nbt.remediation.policy")

VALID_MODES = ("simulate", "ansible")
VERIFIABLE = ("verifying", "verification_inconclusive", "verification_failed")
OUTCOME_STATUS = {"passed": "resolved", "failed": "verification_failed",
                  "inconclusive": "verification_inconclusive", "not_applicable": "completed"}


def resolve_mode(explicit: Optional[str] = None) -> str:
    mode = (explicit or os.environ.get("NBT_REMEDIATION_MODE") or "simulate").strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"NBT_REMEDIATION_MODE must be one of {VALID_MODES}, got {mode!r}")
    return mode


class _Reject(Exception):
    pass


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


class RemediationPolicy:
    def __init__(
        self,
        store: Optional[ProposalStore] = None,
        registry: Optional[TopologyRegistry] = None,
        mode: Optional[str] = None,
        approval_ttl_s: Optional[int] = None,
        inventory: Optional[Iterable[str]] = None,
        executor_factory: Callable[[str], Any] = executor_for,
    ):
        self.store = store or ProposalStore()
        self.registry = registry or get_registry()
        self.mode = resolve_mode(mode)
        self.ttl_s = int(approval_ttl_s or os.environ.get("NBT_APPROVAL_TTL_SECONDS", "3600"))
        self._inventory = set(inventory) if inventory is not None else None
        self._executor_factory = executor_factory

    def inventory(self) -> set:
        if self._inventory is None:
            self._inventory = inventory_hosts()
        return self._inventory

    # ------------------------------------------------------------------
    # Validation + preview
    # ------------------------------------------------------------------
    def validate(self, candidate: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Return a preview for an acceptable candidate or raise ``_Reject``."""
        spec = action_for(candidate)
        if spec is None:
            raise _Reject(f"'{candidate.get('action') or candidate.get('playbook')}' is not an allowlisted action")
        domain = evidence.get("inference", {}).get("fault_domain", "UNKNOWN")
        if domain not in spec.applicable_domains:
            raise _Reject(f"{spec.action} is not applicable to fault domain {domain}")
        loc = evidence.get("localization", {})
        host = (loc.get("host") or {}).get("name")
        if not valid_host(host):
            raise _Reject("host name is missing or contains unsafe characters")
        if not (loc.get("host") or {}).get("resolved") or self.registry.host(host) is None:
            raise _Reject(f"host '{host}' is not in the approved topology inventory")
        if self.mode == "ansible" and host not in self.inventory():
            raise _Reject(f"host '{host}' is not in infra/inventory.ini [agents]")
        for t in candidate.get("targets") or []:
            if isinstance(t, dict) and t.get("host") not in (None, host):
                raise _Reject(f"requested target host '{t.get('host')}' is outside this incident")

        if spec.action == "set_mtu":
            hint = evidence.get("remediation_hint") or {}
            if hint.get("action") != "set_mtu":
                raise _Reject("no confirmed MTU mismatch between telemetry and topology intent")
            targets = []
            for t in hint.get("targets", []):
                if not valid_iface(t.get("iface")) or self.registry.interface(t.get("host"), t.get("iface")) is None:
                    raise _Reject(f"interface '{t.get('iface')}' is invalid or not in topology")
                targets.append({"host": t["host"], "iface": t["iface"]})
            wanted = {(t["host"], t["iface"]) for t in targets}
            for t in candidate.get("targets") or []:
                if isinstance(t, dict) and t.get("iface") and (t.get("host") or host, t["iface"]) not in wanted:
                    raise _Reject(f"requested interface '{t['iface']}' does not match the localized fault")
            desired = hint.get("desired_mtu")
            if not valid_mtu(desired):
                raise _Reject(f"desired MTU {desired!r} is outside the allowed range")
            params = {"desired_mtu": desired}
            extra_vars = {"targets": targets, "desired_mtu": desired}
        elif spec.action == "restart_driver":
            drivers = sorted({i.get("driver") for i in loc.get("interfaces", []) if i.get("resolved")} - {None})
            if not drivers:
                raise _Reject("no resolved interface; the driver to reload is unknown")
            bad = [d for d in drivers if d not in DRIVER_ALLOWLIST]
            if bad:
                raise _Reject(f"driver(s) {bad} are not allowlisted")
            targets = [{"host": host, "driver": d} for d in drivers]
            params = {}
            extra_vars = {"targets": targets}
        else:  # collect_forensics
            targets = [{"host": host}]
            params = {}
            extra_vars = {"targets": targets, "tcpdump_duration": 0}

        limit = sorted({t["host"] for t in targets})
        blast = (evidence.get("scope") or {}).get("blast_radius", [])
        ignored = sorted(k for k in ("extra_vars", "reason", "vars") if candidate.get(k))
        preview = {
            "action": spec.action,
            "description": spec.description,
            "playbook": spec.playbook,
            "mode": self.mode,
            "simulated": self.mode == "simulate",
            "targets": targets,
            "limit": limit,
            "params": params,
            "extra_vars": extra_vars,
            "changes_state": spec.changes_state,
            "risk": spec.risk,
            "risk_rationale": (
                f"{spec.risk} risk: {'changes host state' if spec.changes_state else 'read-only collection'} on "
                f"{', '.join(limit)}; {len(blast)} entit{'y' if len(blast) == 1 else 'ies'} in the blast radius. "
                "Shared switch configuration is not modified."
            ),
            "requires_approval": True,
            "shared_infrastructure_changed": False,
            "blast_radius": blast,
            "rollback": spec.rollback,
            "post_check": spec.post_check,
            "command_preview": " ".join([
                "ansible-playbook", "-i", "infra/inventory.ini", f"infra/playbooks/{spec.playbook}",
                "--limit", ",".join(limit), "--extra-vars", shlex.quote(json.dumps(extra_vars, sort_keys=True)),
            ]),
            "ignored_inputs": ignored,
        }
        return preview

    # ------------------------------------------------------------------
    def propose(
        self,
        *,
        source: str,
        event: Dict[str, Any],
        evidence: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        incident_ref: Optional[str] = None,
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        considered, chosen, recommenders = [], None, []
        for c in candidates:
            entry = {"recommender": c.get("recommender"), "requested": c.get("action") or c.get("playbook")}
            try:
                preview = self.validate(c, evidence)
            except _Reject as exc:
                considered.append({**entry, "accepted": False, "reason": str(exc)})
                continue
            if chosen is None:
                chosen = preview
            if (preview["action"], preview["targets"]) == (chosen["action"], chosen["targets"]):
                recommenders.append(c.get("recommender"))
                considered.append({**entry, "accepted": True, "reason": "passed policy validation"})
            else:
                considered.append({**entry, "accepted": False,
                                   "reason": f"valid, but conflicts with the selected {chosen['action']} proposal"})
        recommenders = sorted(set(r for r in recommenders if r))

        target_key = f"{chosen['action']}|{json.dumps(chosen['targets'], sort_keys=True)}" if chosen else None
        pid = "rem-" + hashlib.sha1(f"{event.get('event_id')}|{target_key or 'blocked'}".encode()).hexdigest()[:12]
        existing = self.store.get(pid)
        if existing:
            return {**existing, "deduplicated": True}
        if target_key:
            open_p = self.store.find_open(target_key)
            if open_p:
                self.store.audit("duplicate_suppressed", open_p,
                                 {"event_id": event.get("event_id"), "source": source})
                return {**open_p, "deduplicated": True}

        now = datetime.now(timezone.utc)
        inf = evidence.get("inference", {})
        proposal = {
            "id": pid,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.ttl_s)).isoformat(),
            "status": "pending_approval" if chosen else "blocked",
            "source": source,
            "incident_ref": incident_ref,
            "event_id": event.get("event_id"),
            "host": event.get("host"),
            "scenario_id": scenario_id,
            "simulated_evidence": bool(event.get("simulated")),
            "mode": self.mode,
            "target_key": target_key,
            "recommenders": recommenders,
            "candidates_considered": considered,
            "block_reason": None if chosen else "; ".join(c["reason"] for c in considered) or "no candidates",
            "preview": chosen,
            "preview_digest": _digest(chosen) if chosen else None,
            "diagnosis": {"fault_domain": inf.get("fault_domain"), "status": inf.get("status"),
                          "statement": inf.get("statement"),
                          "confidence": (evidence.get("confidence") or {}).get("level")},
            "before_event": {k: event.get(k) for k in ("event_id", "host", "ts", "ifaces", "rdma", "simulated")},
            "decision": None,
            "execution": None,
            "verification": None,
        }
        if not self.store.insert(proposal):
            return {**(self.store.get(pid) or proposal), "deduplicated": True}
        self.store.audit("recommended", proposal, {"source": source, "candidates": considered,
                                                   "diagnosis": proposal["diagnosis"]})
        if chosen:
            self.store.audit("previewed", proposal, {"preview_digest": proposal["preview_digest"],
                                                     "action": chosen["action"], "targets": chosen["targets"],
                                                     "mode": self.mode, "risk": chosen["risk"]})
        else:
            self.store.audit("blocked", proposal, {"reason": proposal["block_reason"]})
        LOG.info("Remediation proposal %s status=%s source=%s", pid, proposal["status"], source)
        return proposal

    # ------------------------------------------------------------------
    def decide(
        self,
        proposal_id: str,
        *,
        approved: bool,
        approver: str,
        preview_digest: Optional[str] = None,
        reason: Optional[str] = None,
        post_telemetry: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        if not valid_approver(approver):
            return {"error": "approver is required (1-64 chars: letters, digits, space, . _ @ -)"}, 400
        p = self.store.get(proposal_id)
        if p is None:
            return {"error": "proposal not found"}, 404
        if p["status"] != "pending_approval":
            return {"error": f"proposal is '{p['status']}'; it cannot be decided again", "proposal": p}, 409
        if datetime.now(timezone.utc) > datetime.fromisoformat(p["expires_at"]):
            expired = self.store.transition(proposal_id, "pending_approval", {"status": "expired"})
            self.store.audit("expired", p, {"expires_at": p["expires_at"]}, actor=approver)
            return {"error": "proposal expired; re-run triage to get a fresh preview",
                    "proposal": expired or self.store.get(proposal_id)}, 409
        if preview_digest and preview_digest != p["preview_digest"]:
            return {"error": "preview changed since it was reviewed; reload and review again", "proposal": p}, 409
        if approved and p["mode"] == "ansible" and self.mode != "ansible":
            return {"error": "proposal was previewed for real execution but this process is not configured for "
                             "NBT_REMEDIATION_MODE=ansible", "proposal": p}, 409

        decision = {"approved": bool(approved), "approver": approver, "ts": iso_now(),
                    "reason": (reason or "")[:500] or None}
        p2 = self.store.transition(proposal_id, "pending_approval",
                                   {"status": "approved" if approved else "rejected", "decision": decision})
        if p2 is None:
            return {"error": "proposal was decided concurrently", "proposal": self.store.get(proposal_id)}, 409
        self.store.audit("approved" if approved else "rejected", p2, {"reason": decision["reason"],
                                                                      "preview_digest": p2["preview_digest"]},
                         actor=approver)
        if not approved:
            return p2, 200

        p3 = self.store.transition(proposal_id, "approved", {"status": "executing"})
        try:
            result = self._executor_factory(p3["mode"]).run(p3["preview"])
        except Exception as exc:  # executor failures must be visible, never swallowed
            LOG.exception("Executor failed for %s", proposal_id)
            result = {"ok": False, "mode": p3["mode"], "simulated": p3["mode"] == "simulate",
                      "detail": f"executor error: {type(exc).__name__}: {exc}", "phases": []}
        result["ts"] = iso_now()
        self.store.audit("simulated" if result.get("simulated") else "executed", p3, result, actor=approver)
        if not result.get("ok"):
            return self.store.transition(proposal_id, "executing",
                                         {"status": "execution_failed", "execution": result}), 200
        self.store.transition(proposal_id, "executing", {"status": "verifying", "execution": result})
        samples = post_telemetry(p3) if post_telemetry else []
        return self.verify(proposal_id, samples)

    def verify(self, proposal_id: str, post_samples: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], int]:
        p = self.store.get(proposal_id)
        if p is None:
            return {"error": "proposal not found"}, 404
        if p["status"] not in VERIFIABLE:
            return {"error": f"proposal is '{p['status']}'; nothing to verify", "proposal": p}, 409
        prev = p["preview"]
        res = run_post_check(prev["action"], prev["targets"], prev["params"], p.get("before_event"),
                             post_samples or [])
        res["ts"] = iso_now()
        res["simulated_samples"] = any(bool(s.get("simulated")) for s in post_samples or [])
        if p["execution"] and p["execution"].get("simulated"):
            res["note"] = ("Execution was simulated; post-check samples " +
                           ("are scripted scenario fixtures." if res["simulated_samples"]
                            else "come from ingested telemetry and will not reflect a change that was not made."))
        updated = self.store.transition(proposal_id, p["status"],
                                        {"status": OUTCOME_STATUS[res["outcome"]], "verification": res})
        if updated is None:
            return {"error": "proposal changed concurrently", "proposal": self.store.get(proposal_id)}, 409
        self.store.audit("post_check", updated, {"outcome": res["outcome"], "checks": res["checks"]})
        return updated, 200

    # ------------------------------------------------------------------
    def get(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get(proposal_id)

    def list(self, limit: int = 50, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.store.list(limit=limit, scenario_id=scenario_id)

    def audit(self, limit: int = 100, proposal_id: Optional[str] = None,
              scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.store.audit_entries(limit=limit, proposal_id=proposal_id, scenario_id=scenario_id)

    def reset_scenario(self, scenario_id: str) -> int:
        return self.store.delete_scenario(scenario_id)


def summarize(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Compact view embedded in triage decisions."""
    if not p:
        return None
    prev = p.get("preview") or {}
    return {
        "id": p["id"],
        "status": p["status"],
        "action": prev.get("action"),
        "playbook": prev.get("playbook"),
        "targets": prev.get("targets"),
        "risk": prev.get("risk"),
        "mode": p.get("mode"),
        "requires_approval": bool(prev),
        "block_reason": p.get("block_reason"),
        "outcome": (p.get("verification") or {}).get("outcome"),
        "recommenders": p.get("recommenders"),
    }
