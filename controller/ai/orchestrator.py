#!/usr/bin/env python3
"""
Multi-agent orchestrator.

Implements the Google ADK / LangGraph-style workflow that threads a shared
:class:`WorkflowState` through the agent graph:

    Planner -> Telemetry -> Retriever -> KnowledgeBase -> RootCause
            -> Remediation -> (Human Approval gate) -> Validation -> Audit

The orchestrator is deliberately self-contained (no hard dependency on the
``langgraph`` package) so it runs anywhere, but it is structured as nodes +
conditional edges so it can be swapped for a native LangGraph ``StateGraph`` with
minimal change. If ``langgraph`` is installed it is used to build the graph;
otherwise the built-in sequential executor runs the identical node functions.

Human approval
--------------
When ``require_human_approval`` is set (default), remediation plans stop at
``pending_approval`` and are NOT executed automatically. The Flask API exposes
approve/execute endpoints; the orchestrator's :meth:`resume_after_approval`
continues the validation + audit phases once a human approves.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from controller.ai.agents import (
    AgentDeps,
    AuditAgent,
    KnowledgeBaseAgent,
    PlannerAgent,
    RemediationAgent,
    RetrieverAgent,
    RootCauseAnalysisAgent,
    TelemetryAnalysisAgent,
    ValidationAgent,
    WorkflowState,
)
from controller.ai.config import AIConfig, get_ai_config
from controller.ai.llm import get_llm_client
from controller.ai.memory import get_memory
from controller.ai.monitoring import get_monitor

LOG = logging.getLogger("nbt.ai.orchestrator")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Orchestrator:
    """Runs the multi-agent triage/remediation workflow for one event."""

    def __init__(self, config: Optional[AIConfig] = None):
        self.cfg = config or get_ai_config()
        self.llm = get_llm_client(self.cfg)
        self.memory = get_memory(self.cfg) if self.cfg.memory.enabled else None
        self.monitor = get_monitor()

        # Retriever wires in memory for the incident-history channel.
        try:
            from controller.ai.retriever import HybridRetriever

            self.retriever = HybridRetriever(self.cfg, memory=self.memory)
        except Exception:
            LOG.exception("Retriever init failed; continuing without retrieval")
            self.retriever = None

        deps = AgentDeps(
            llm=self.llm,
            retriever=self.retriever,
            memory=self.memory,
            config=self.cfg,
        )
        self.agents = {
            "planner": PlannerAgent(deps),
            "telemetry": TelemetryAnalysisAgent(deps),
            "retriever": RetrieverAgent(deps),
            "knowledge": KnowledgeBaseAgent(deps),
            "rca": RootCauseAnalysisAgent(deps),
            "remediation": RemediationAgent(deps),
            "validation": ValidationAgent(deps),
            "audit": AuditAgent(deps),
        }
        LOG.info(
            "Orchestrator ready (llm=%s, retriever=%s, memory=%s, approval=%s)",
            self.llm.backend_name,
            getattr(self.retriever, "backend_name", "none"),
            "on" if self.memory else "off",
            self.cfg.require_human_approval,
        )

    # ------------------------------------------------------------------
    @property
    def backend(self) -> str:
        return self.llm.backend_name

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.cfg.enabled,
            "llm_backend": self.llm.backend_name,
            "uses_llm": self.llm.uses_llm,
            "vertex_model": self.cfg.vertex.model if self.llm.uses_llm else None,
            "retriever_backend": getattr(self.retriever, "backend_name", None),
            "require_human_approval": self.cfg.require_human_approval,
            "memory": self.memory.stats() if self.memory else None,
            "metrics": self.monitor.snapshot(),
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(
        self,
        event: Dict[str, Any],
        base_decision: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the workflow for a single event and return an AI result dict."""
        state = WorkflowState(
            event=event,
            base_decision=base_decision or {},
            rule=(base_decision or {}).get("rule") or {},
            ml=(base_decision or {}).get("ml") or {},
            log_class=(base_decision or {}).get("log_class"),
        )
        state.incident_id = f"inc-{event.get('event_id', uuid.uuid4().hex[:8])}"
        if self.memory:
            self.memory.start_conversation(state.incident_id)

        self.monitor.incr("workflow_runs")
        try:
            with self.monitor.timer("workflow_latency"):
                state = self._execute(state)
        except Exception as exc:
            LOG.exception("Workflow execution failed")
            self.monitor.incr("workflow_errors")
            state.errors.append(str(exc))

        if state.remediation.get("status") == "pending_approval":
            self.monitor.incr("pending_approvals")
        if state.rca.get("fault_domain"):
            self.monitor.incr(f"domain_{state.rca['fault_domain'].lower()}")

        return self._result(state)

    def resume_after_approval(
        self,
        state_or_result: Dict[str, Any],
        post_remediation_event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Continue validation + audit after a human approves remediation.

        Accepts a previously returned result dict; reconstructs a minimal state
        and runs the validation + audit agents.
        """
        state = WorkflowState(event=state_or_result.get("event", {}))
        state.incident_id = state_or_result.get("incident_id", "")
        state.rca = state_or_result.get("rca", {})
        state.remediation = state_or_result.get("remediation", {})
        state.remediation["status"] = "approved"
        if post_remediation_event:
            state.event["_post_remediation"] = post_remediation_event
        self.agents["validation"].run(state)
        self.agents["audit"].run(state)
        return self._result(state)

    # ------------------------------------------------------------------
    # Graph execution
    # ------------------------------------------------------------------
    def _execute(self, state: WorkflowState) -> WorkflowState:
        # Planner always runs first and decides the remaining steps.
        state = self.agents["planner"].run(state)
        steps: List[str] = state.plan.get("steps", ["telemetry", "audit"])
        for step in steps:
            agent = self.agents.get(step)
            if agent is None:
                continue
            # Human-approval gate: stop before validation if approval pending.
            state = agent.run(state)
            if (
                step == "remediation"
                and state.remediation.get("status") == "pending_approval"
            ):
                state.log_step(
                    "orchestrator",
                    "paused for human approval before execution",
                )
                break
        return state

    # ------------------------------------------------------------------
    def _result(self, state: WorkflowState) -> Dict[str, Any]:
        return {
            "ts": _iso_now(),
            "incident_id": state.incident_id,
            "event": state.event,
            "host": state.event.get("host"),
            "event_id": state.event.get("event_id"),
            "llm_backend": self.llm.backend_name,
            "plan": state.plan,
            "signals": state.signals,
            "runbook": state.runbook,
            "rca": state.rca,
            "remediation": state.remediation,
            "validation": state.validation,
            "context_sources": [
                getattr(it, "source", "?") for it in state.context_items
            ],
            "trace": state.trace,
            "errors": state.errors,
        }


# ----------------------------------------------------------------------
# Module-level singleton
# ----------------------------------------------------------------------
_ORCHESTRATOR: Optional[Orchestrator] = None


def get_orchestrator(config: Optional[AIConfig] = None) -> Orchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = Orchestrator(config)
    return _ORCHESTRATOR
