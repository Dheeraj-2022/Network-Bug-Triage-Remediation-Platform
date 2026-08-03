#!/usr/bin/env python3
"""
Multi-agent definitions.

Each agent is a small, single-responsibility unit that reads from and writes to a
shared :class:`WorkflowState`. This mirrors the Google ADK / LangGraph "agents as
graph nodes over shared state" pattern while remaining dependency-free.

Agents
------
* :class:`PlannerAgent`             – decides which downstream agents to run.
* :class:`TelemetryAnalysisAgent`   – extracts structured signals from the event.
* :class:`RetrieverAgent`           – hybrid retrieval of grounding context.
* :class:`KnowledgeBaseAgent`       – selects the authoritative runbook.
* :class:`RootCauseAnalysisAgent`   – LLM (Gemini) root-cause reasoning.
* :class:`RemediationAgent`         – LLM remediation planning + risk analysis.
* :class:`ValidationAgent`          – post-remediation validation.
* :class:`AuditAgent`               – writes incident/remediation memory + audit.

The XGBoost result and rule-engine result are passed in as-is: the LLM agents
*augment* them, they never replace the fast classifier.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("nbt.ai.agents")

# Playbooks that physically exist in the repo (source of truth for planning).
_PLAYBOOK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "infra",
    "playbooks",
)

# Mapping from fault domain to the canonical remediation playbook.
_DOMAIN_PLAYBOOK = {
    "MTU_MISMATCH": "remediate_mtu.yml",
    "RDMA_ERROR": "remediate_mtu.yml",  # RDMA QP errors usually stem from MTU/PFC
    "DRIVER_FAULT": "restart_driver.yml",
    "LINK_FLAP": "restart_driver.yml",
    "CONGESTION": "remediate_mtu.yml",
    # Panics are never auto-remediated -> forensics + human.
    "KERNEL_PANIC": None,
    "UNKNOWN": None,
}

# Domains we refuse to auto-remediate regardless of confidence.
_NON_AUTOREMEDIABLE = {"KERNEL_PANIC", "UNKNOWN"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowState:
    """Shared state threaded through the agent graph."""

    event: Dict[str, Any]
    base_decision: Dict[str, Any] = field(default_factory=dict)
    rule: Dict[str, Any] = field(default_factory=dict)
    ml: Dict[str, Any] = field(default_factory=dict)
    log_class: Optional[str] = None

    # Populated by agents:
    incident_id: str = ""
    signals: Dict[str, Any] = field(default_factory=dict)
    plan: Dict[str, Any] = field(default_factory=dict)
    context_items: List[Any] = field(default_factory=list)
    context_text: str = ""
    runbook: Optional[str] = None
    rca: Dict[str, Any] = field(default_factory=dict)
    remediation: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def log_step(self, agent: str, message: str, data: Any = None) -> None:
        self.trace.append(
            {"ts": _iso_now(), "agent": agent, "message": message, "data": data}
        )


class BaseAgent:
    name = "base"

    def __init__(self, deps: "AgentDeps"):
        self.deps = deps

    def run(self, state: WorkflowState) -> WorkflowState:  # pragma: no cover
        raise NotImplementedError


@dataclass
class AgentDeps:
    """Shared dependencies injected into every agent."""

    llm: Any
    retriever: Any
    memory: Any
    config: Any


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class PlannerAgent(BaseAgent):
    """Decides the depth of analysis based on severity signals."""

    name = "planner"

    def run(self, state: WorkflowState) -> WorkflowState:
        ml_priority = float(state.ml.get("priority_score", 0.0))
        rule_action = state.rule.get("action", "none")
        escalate = (
            ml_priority >= self.deps.config.escalation_priority
            or rule_action == "remediate"
        )
        state.plan = {
            "escalate": escalate,
            "steps": (
                ["telemetry", "retriever", "knowledge", "rca", "remediation", "audit"]
                if escalate
                else ["telemetry", "audit"]
            ),
            "reason": (
                f"ml_priority={ml_priority:.2f} rule_action={rule_action}"
            ),
        }
        if self.deps.memory:
            self.deps.memory.add_message(
                state.incident_id, "planner", json.dumps(state.plan)
            )
        state.log_step(self.name, "planned workflow", state.plan)
        return state


class TelemetryAnalysisAgent(BaseAgent):
    """Extracts structured signals (counters, anomalies) from the raw event."""

    name = "telemetry"

    def run(self, state: WorkflowState) -> WorkflowState:
        ev = state.event
        iface_summary = []
        max_err = 0
        for nic, st in (ev.get("ifaces") or {}).items():
            err = int(st.get("errin", 0)) + int(st.get("errout", 0))
            max_err = max(max_err, err)
            iface_summary.append(
                {
                    "iface": nic,
                    "errors": err,
                    "mtu": int(st.get("mtu", 1500)),
                }
            )
        rdma = ev.get("rdma") or {}
        qp = int(rdma.get("qp_errors", 0))
        state.signals = {
            "host": ev.get("host"),
            "max_iface_errors": max_err,
            "rdma_qp_errors": qp,
            "ifaces": iface_summary,
            "log_class": state.log_class,
            "dmesg_tail": ev.get("dmesg_tail", ""),
            "mtu_anomaly": any(i["mtu"] not in (1500, 9000) for i in iface_summary),
        }
        state.log_step(self.name, "extracted signals", state.signals)
        return state


class RetrieverAgent(BaseAgent):
    """Runs hybrid retrieval to ground downstream reasoning."""

    name = "retriever"

    def run(self, state: WorkflowState) -> WorkflowState:
        if self.deps.retriever is None:
            state.log_step(self.name, "retriever unavailable")
            return state
        query = self._build_query(state)
        provisional_domain = self.deps.llm.heuristic.classify_fault(
            state.signals.get("dmesg_tail", ""), state.rule
        )
        items = self.deps.retriever.retrieve(
            query=query,
            host=state.signals.get("host"),
            fault_domain=provisional_domain,
        )
        state.context_items = items
        state.context_text = self.deps.retriever.format_context(items)
        state.signals["provisional_domain"] = provisional_domain
        state.log_step(
            self.name,
            f"retrieved {len(items)} items via {self.deps.retriever.backend_name}",
            [it.source for it in items],
        )
        return state

    @staticmethod
    def _build_query(state: WorkflowState) -> str:
        sig = state.signals
        return (
            f"host={sig.get('host')} log_class={sig.get('log_class')} "
            f"dmesg={sig.get('dmesg_tail')} "
            f"iface_errors={sig.get('max_iface_errors')} "
            f"rdma_qp_errors={sig.get('rdma_qp_errors')}"
        )


class KnowledgeBaseAgent(BaseAgent):
    """Selects the authoritative runbook for the provisional fault domain."""

    name = "knowledge"

    def run(self, state: WorkflowState) -> WorkflowState:
        domain = state.signals.get("provisional_domain", "UNKNOWN")
        # Prefer a retrieved runbook chunk matching the domain.
        for it in state.context_items:
            if it.metadata.get("category") == "runbooks":
                state.runbook = it.source
                break
        state.signals["kb_runbook"] = state.runbook
        state.log_step(
            self.name, f"selected runbook for {domain}", state.runbook
        )
        return state


class RootCauseAnalysisAgent(BaseAgent):
    """LLM-driven root-cause analysis (Gemini) grounded in retrieved context."""

    name = "rca"

    def run(self, state: WorkflowState) -> WorkflowState:
        provisional = state.signals.get("provisional_domain", "UNKNOWN")
        memory_summary = ""
        if self.deps.memory:
            memory_summary = self.deps.memory.summary(
                host=state.signals.get("host"), fault_domain=provisional
            )
        fallback = self._heuristic_rca(state, provisional, memory_summary)
        rca = self.deps.llm.generate_json(
            "root_cause_analysis",
            event_json=json.dumps(state.event, default=str)[:4000],
            ml_json=json.dumps(state.ml, default=str),
            rule_json=json.dumps(state.rule, default=str),
            context=state.context_text[:6000],
            memory=memory_summary,
            _fallback=fallback,
        )
        # Ensure required keys always present.
        for key, default in fallback.items():
            rca.setdefault(key, default)
        state.rca = rca
        if self.deps.memory:
            self.deps.memory.add_message(
                state.incident_id, "rca", json.dumps(rca, default=str)
            )
        state.log_step(
            self.name,
            f"root cause: {rca.get('fault_domain')} "
            f"(conf={rca.get('confidence')}, backend={rca.get('_backend')})",
        )
        return state

    def _heuristic_rca(
        self, state: WorkflowState, provisional: str, memory_summary: str
    ) -> Dict[str, Any]:
        sig = state.signals
        evidence = []
        if sig.get("rdma_qp_errors"):
            evidence.append(f"rdma qp_errors={sig['rdma_qp_errors']}")
        if sig.get("max_iface_errors"):
            evidence.append(f"iface errors={sig['max_iface_errors']}")
        if sig.get("mtu_anomaly"):
            evidence.append("non-standard MTU detected")
        if sig.get("dmesg_tail"):
            evidence.append(f"dmesg: {sig['dmesg_tail'][:120]}")
        # Confidence blends the XGBoost priority with evidence strength.
        ml_priority = float(state.ml.get("priority_score", 0.0))
        confidence = round(min(0.95, 0.4 + 0.4 * ml_priority + 0.05 * len(evidence)), 3)
        explanation = (
            f"Provisional domain {provisional} inferred from kernel log signature "
            f"and telemetry counters on host {sig.get('host')}. "
            f"XGBoost priority {ml_priority:.2f}. {memory_summary}"
        )
        return {
            "root_cause": f"{provisional} on {sig.get('host')}",
            "fault_domain": provisional,
            "confidence": confidence,
            "evidence": evidence or ["no strong counter signal"],
            "explanation": explanation,
        }


class RemediationAgent(BaseAgent):
    """LLM remediation planning + risk analysis, constrained to real playbooks."""

    name = "remediation"

    def run(self, state: WorkflowState) -> WorkflowState:
        domain = state.rca.get("fault_domain", "UNKNOWN")
        available = _available_playbooks()
        targets = self._targets(state)
        fallback = self._heuristic_plan(state, domain, targets)
        plan = self.deps.llm.generate_json(
            "remediation_plan",
            rca_json=json.dumps(state.rca, default=str),
            playbooks=json.dumps(available),
            targets=json.dumps(targets, default=str),
            _fallback=fallback,
        )
        for key, default in fallback.items():
            plan.setdefault(key, default)

        # Safety guardrails — never let the LLM select an unknown or unsafe path.
        playbook = plan.get("playbook")
        if playbook and playbook not in available:
            LOG.warning("LLM proposed unknown playbook %s; overriding", playbook)
            playbook = fallback["playbook"]
            plan["playbook"] = playbook
            plan["risk_rationale"] = (
                "Overridden to a known playbook by safety guardrail. "
                + str(plan.get("risk_rationale", ""))
            )
        if domain in _NON_AUTOREMEDIABLE:
            plan["playbook"] = None
            plan["requires_human_approval"] = True
            plan["risk"] = "high"

        # Human-approval gate.
        if self.deps.config.require_human_approval:
            plan["requires_human_approval"] = True
        plan["targets"] = targets
        plan["status"] = (
            "pending_approval"
            if plan.get("requires_human_approval") and plan.get("playbook")
            else ("auto" if plan.get("playbook") else "no_action")
        )
        state.remediation = plan
        if self.deps.memory:
            self.deps.memory.add_message(
                state.incident_id, "remediation", json.dumps(plan, default=str)
            )
        state.log_step(
            self.name,
            f"plan: playbook={plan.get('playbook')} risk={plan.get('risk')} "
            f"status={plan.get('status')}",
        )
        return state

    def _targets(self, state: WorkflowState) -> List[Dict[str, Any]]:
        targets = state.rule.get("targets") or []
        if targets:
            return targets
        host = state.signals.get("host")
        return [{"host": host}] if host else []

    def _heuristic_plan(
        self, state: WorkflowState, domain: str, targets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        # Prefer what history says works best, else domain default.
        best = None
        if self.deps.memory:
            best = self.deps.memory.best_playbook_for(domain)
        playbook = best or _DOMAIN_PLAYBOOK.get(domain)
        available = _available_playbooks()
        if playbook not in available:
            playbook = None if domain in _NON_AUTOREMEDIABLE else (
                available[0] if available else None
            )
        risk = "high" if domain in _NON_AUTOREMEDIABLE else (
            "medium" if domain in ("DRIVER_FAULT", "LINK_FLAP") else "low"
        )
        extra_vars: Dict[str, Any] = {"reason": state.rca.get("root_cause")}
        if domain in ("MTU_MISMATCH", "RDMA_ERROR", "CONGESTION"):
            extra_vars["target_mtu"] = 9000 if state.signals.get(
                "rdma_qp_errors"
            ) else 1500
        return {
            "playbook": playbook,
            "strategy": "canary",
            "extra_vars": extra_vars,
            "risk": risk,
            "risk_rationale": (
                f"Domain {domain}; canary rollout limits blast radius."
                if playbook
                else f"Domain {domain} is not safe to auto-remediate."
            ),
            "requires_human_approval": risk != "low",
            "rollback": "Re-apply prior config captured in remediation audit log.",
        }


class ValidationAgent(BaseAgent):
    """Validates whether a remediation resolved the fault (before/after)."""

    name = "validation"

    def run(self, state: WorkflowState) -> WorkflowState:
        after = state.event.get("_post_remediation") or {}
        fallback = self._heuristic_validation(state, after)
        result = self.deps.llm.generate_json(
            "validation",
            plan_json=json.dumps(state.remediation, default=str),
            before_json=json.dumps(state.event, default=str)[:3000],
            after_json=json.dumps(after, default=str)[:2000],
            _fallback=fallback,
        )
        for key, default in fallback.items():
            result.setdefault(key, default)
        state.validation = result
        state.log_step(
            self.name,
            f"validation: resolved={result.get('resolved')} "
            f"conf={result.get('confidence')}",
        )
        return state

    @staticmethod
    def _heuristic_validation(
        state: WorkflowState, after: Dict[str, Any]
    ) -> Dict[str, Any]:
        # With no post-remediation telemetry we report an optimistic-but-flagged
        # provisional result pending the next telemetry cycle.
        if not after:
            return {
                "resolved": None,
                "confidence": 0.0,
                "residual_risk": "awaiting post-remediation telemetry",
                "recommendation": "Re-evaluate on next telemetry cycle.",
            }
        qp = int((after.get("rdma") or {}).get("qp_errors", 0))
        errs = sum(
            int(s.get("errin", 0)) + int(s.get("errout", 0))
            for s in (after.get("ifaces") or {}).values()
        )
        resolved = qp == 0 and errs == 0
        return {
            "resolved": resolved,
            "confidence": 0.7 if resolved else 0.4,
            "residual_risk": "none" if resolved else "counters still incrementing",
            "recommendation": (
                "Close incident." if resolved else "Escalate to on-call."
            ),
        }


class AuditAgent(BaseAgent):
    """Persists the incident to memory and emits an audit summary."""

    name = "audit"

    def run(self, state: WorkflowState) -> WorkflowState:
        incident = {
            "incident_id": state.incident_id,
            "event_id": state.event.get("event_id"),
            "host": state.event.get("host"),
            "fault_domain": state.rca.get("fault_domain"),
            "root_cause": state.rca.get("root_cause"),
            "confidence": state.rca.get("confidence"),
            "playbook": state.remediation.get("playbook"),
            "risk": state.remediation.get("risk"),
            "status": state.remediation.get("status"),
            "resolved": state.validation.get("resolved"),
            "backend": state.rca.get("_backend"),
            "ts": _iso_now(),
        }
        if self.deps.memory:
            self.deps.memory.record_incident(incident)
        state.log_step(self.name, "recorded incident to memory", incident)
        state.base_decision["ai_incident"] = incident
        return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _available_playbooks() -> List[str]:
    try:
        return sorted(
            f
            for f in os.listdir(_PLAYBOOK_DIR)
            if f.endswith(".yml") and not f.startswith("rollback_")
        )
    except Exception:
        return ["remediate_mtu.yml", "restart_driver.yml", "collect_forensics.yml"]
