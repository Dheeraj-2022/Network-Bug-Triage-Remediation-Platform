"""
NetResolve AI application awareness and interactive 12-stage walkthrough.

Grounded strictly in the actual NetResolve AI codebase architecture. Used both
by authenticated operators inside Voice Operations and by anonymous visitors
seeking an introductory walkthrough without exposing protected infrastructure.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

WALKTHROUGH_STAGES: List[Dict[str, Any]] = [
    {
        "step": 1,
        "id": "telemetry_ingestion",
        "title": "Telemetry Ingestion",
        "route": "events",
        "route_label": "Telemetry Events",
        "summary": (
            "Host telemetry agents collect interface counters (rx/tx bytes, errin, errout, MTU), "
            "RDMA queue-pair error counters, kernel dmesg log tails, and packet samples."
        ),
        "details": (
            "Events arrive via Kafka or the FastAPI /api/process and /api/inject endpoints. "
            "Simulated fixtures are explicitly tagged so they are never confused with live telemetry."
        ),
    },
    {
        "step": 2,
        "id": "event_processing",
        "title": "Event Processing Pipeline",
        "route": "events",
        "route_label": "Telemetry Events",
        "summary": (
            "The central controller processor normalizes incoming events, tracks per-host baselines, "
            "and feeds each sample through deterministic rules, ML triage, evidence generation, and AI analysis."
        ),
        "details": (
            "Implemented in controller/processor.py and api/service.py, preserving chronological "
            "history for delta calculations and post-remediation verification."
        ),
    },
    {
        "step": 3,
        "id": "deterministic_rules",
        "title": "Rule-Based Fault Detection",
        "route": "decisions",
        "route_label": "Triage Decisions",
        "summary": (
            "Deterministic rules evaluate hard thresholds such as interface error spikes (errin + errout) "
            "and RDMA queue-pair error counters to flag immediate remediation candidates."
        ),
        "details": (
            "Rules in controller/rules_engine.py provide transparent, reproducible first-pass "
            "signals that never depend on probabilistic LLM guesses."
        ),
    },
    {
        "step": 4,
        "id": "ml_triage",
        "title": "XGBoost Machine-Learning Triage",
        "route": "ai-analysis",
        "route_label": "Multi-Agent Analysis",
        "summary": (
            "An XGBoost classifier scores incident priority and localizes likely fault domains from "
            "extracted host telemetry features, complemented by NLP log anomaly scoring."
        ),
        "details": (
            "XGBoost acts as a fast statistical triage and prioritization layer (controller/triage_model.py). "
            "It informs priority and localization, but ML scores alone can never bypass RemediationPolicy."
        ),
    },
    {
        "step": 5,
        "id": "evidence_collection",
        "title": "Deterministic Evidence & Topology Correlation",
        "route": "incidents",
        "route_label": "Incident Queue & RCA",
        "summary": (
            "The evidence builder compares observed telemetry against approved topology intent (such as expected "
            "MTU 9000 vs observed 1500), computes counter deltas, parses kernel logs, and correlates recent changes."
        ),
        "details": (
            "Implemented in controller/evidence.py and controller/topology.py. Deterministic facts are kept "
            "strictly separate from model-generated reasoning, and change correlation is explicitly marked as "
            "correlation only — never proof of causation."
        ),
    },
    {
        "step": 6,
        "id": "ai_rca",
        "title": "AI Multi-Agent Root-Cause Analysis",
        "route": "ai-analysis",
        "route_label": "Multi-Agent Analysis",
        "summary": (
            "A LangGraph multi-agent orchestrator powered by Google Gemini on Vertex AI (with an offline "
            "deterministic heuristic fallback) synthesizes signals, evidence, and historical incidents into an RCA."
        ),
        "details": (
            "Implemented in controller/ai/orchestrator.py and controller/ai/agents.py. When Vertex AI "
            "credentials are not configured, the platform transparently runs in offline heuristic mode."
        ),
    },
    {
        "step": 7,
        "id": "knowledge_retrieval",
        "title": "Hybrid Knowledge-Base & Runbook Retrieval",
        "route": "ai-analysis",
        "route_label": "Multi-Agent Analysis",
        "summary": (
            "Hybrid vector and keyword retrieval fetches relevant operational runbooks, RDMA diagnosis guides, "
            "and kernel dmesg patterns to ground the AI analysis."
        ),
        "details": (
            "Implemented in controller/ai/retriever.py and controller/ai/knowledge_base.py, drawing from "
            "curated Markdown runbooks and persistent incident memory."
        ),
    },
    {
        "step": 8,
        "id": "remediation_proposal",
        "title": "Policy-Validated Remediation Proposals",
        "route": "remediation",
        "route_label": "Remediation Gate",
        "summary": (
            "Remediation candidates are validated against the central RemediationPolicy allowlist, fault-domain "
            "applicability, approved topology targets, and safe parameter bounds to produce an exact preview."
        ),
        "details": (
            "The LLM cannot invent arbitrary shell commands or playbooks. Every proposal receives a "
            "SHA-256 preview digest, risk classification, blast radius, rollback plan, and approval expiry."
        ),
    },
    {
        "step": 9,
        "id": "human_approval",
        "title": "Human Authorization Gate",
        "route": "remediation",
        "route_label": "Remediation Gate",
        "summary": (
            "No state-changing remediation executes automatically. An authorized operator must review the "
            "exact target, command preview, and digest, then explicitly approve via the UI or voice readback."
        ),
        "details": (
            "High-risk or shared-infrastructure operations require step-up authorization or a distinct "
            "senior approver. Vague phrases or silence never authorize execution."
        ),
    },
    {
        "step": 10,
        "id": "controlled_execution",
        "title": "Controlled Execution (Simulated / Opt-in Ansible)",
        "route": "remediation",
        "route_label": "Remediation Gate",
        "summary": (
            "Approved proposals run exclusively through RemediationPolicy in the execution mode bound at "
            "preview time — simulated dry-run by default, with live Ansible execution strictly opt-in."
        ),
        "details": (
            "Only the shared RemediationPolicy can invoke the Ansible runner (controller/remediation/executors.py). "
            "Live voice Ansible execution requires explicit NBT_VOICE_ALLOW_ANSIBLE=true and NBT_REMEDIATION_MODE=ansible."
        ),
    },
    {
        "step": 11,
        "id": "post_verification",
        "title": "Deterministic Post-Remediation Verification",
        "route": "demo",
        "route_label": "Two-Host MTU Demo",
        "summary": (
            "After execution, the verification engine checks post-change telemetry (target MTU, error-counter "
            "stabilization, RDMA recovery) before classifying an incident as VERIFIED RESOLVED, FAILED, or INCONCLUSIVE."
        ),
        "details": (
            "Execution success alone never marks an incident resolved. Missing post-change samples produce "
            "VERIFICATION INCONCLUSIVE so operators are never misled."
        ),
    },
    {
        "step": 12,
        "id": "audit_logging",
        "title": "Immutable Redacted Audit Trail",
        "route": "audit-trail",
        "route_label": "Execution & Audit Log",
        "summary": (
            "Every recommendation, preview, human decision, execution phase, post-check result, and voice "
            "transcript is persisted in redacted audit logs."
        ),
        "details": (
            "Secrets and credentials are automatically redacted from transcripts, responses, and audit records."
        ),
    },
]

_TOPIC_PATTERNS: List[tuple[str, re.Pattern[str], int]] = [
    ("xgboost", re.compile(r"\b(xgboost|ml\s+model|machine\s+learning|classifier|priority\s+score|triage\s+model)\b", re.I), 4),
    ("rules", re.compile(r"\b(rules?\s+engine|deterministic\s+rules?|fault\s+detection|thresholds?)\b", re.I), 3),
    ("telemetry", re.compile(r"\b(telemetry|ingest|ingestion|collector|agent\s+collect)\b", re.I), 1),
    ("evidence", re.compile(r"\b(evidence\s+collection|evidence\s+engine|how\s+evidence|topology\s+registry)\b", re.I), 5),
    ("ai_rca", re.compile(r"\b(multi[- ]agent|langgraph|gemini|vertex|how\s+does\s+(the\s+)?(ai|rca|root[- ]cause))\b", re.I), 6),
    ("rag", re.compile(r"\b(knowledge\s+base|runbooks?|retrieval|rag|vector\s+store|memory)\b", re.I), 7),
    ("remediation", re.compile(r"\b(remediation\s+policy|candidates?|how\s+.*remediat|proposal\s+generation)\b", re.I), 8),
    ("approval", re.compile(r"\b(human\s+approval|approval\s+gate|step[- ]up|authorization\s+work)\b", re.I), 9),
    ("ansible", re.compile(r"\b(ansible|playbook\s+execution|how\s+.*execut|simulated\s+mode)\b", re.I), 10),
    ("verification", re.compile(r"\b(post[- ]remediation|post[- ]check|how\s+.*verif)\b", re.I), 11),
    ("audit", re.compile(r"\b(audit\s+log|audit\s+trail|audit\s+records?)\b", re.I), 12),
]


def match_architecture_topic(text: str) -> Optional[Dict[str, Any]]:
    """If the user asks about a specific NetResolve AI subsystem, return its stage."""
    for _name, rx, step_num in _TOPIC_PATTERNS:
        if rx.search(text or ""):
            return WALKTHROUGH_STAGES[step_num - 1]
    return None


def get_walkthrough_stage(step: int) -> Dict[str, Any]:
    idx = max(0, min(len(WALKTHROUGH_STAGES) - 1, step - 1))
    return WALKTHROUGH_STAGES[idx]


def build_app_overview(current_page: Optional[str] = None) -> Dict[str, Any]:
    """Return a concise, accurate overview of NetResolve AI."""
    page_note = f" You are currently viewing the '{current_page}' screen." if current_page else ""
    spoken = (
        "NetResolve AI is an enterprise network bug triage and human-approved remediation platform "
        "built for network operations engineers and GPU/infrastructure SRE teams. "
        "It ingests host interface, RDMA, and kernel telemetry; detects faults using deterministic rules "
        "and an XGBoost triage model; correlates topology intent and recent changes; runs multi-agent "
        "root-cause analysis with runbook retrieval; generates policy-validated remediation previews; "
        "requires explicit human authorization before executing in simulated or opt-in Ansible mode; "
        "and verifies recovery deterministically before marking any incident resolved."
        f"{page_note} Say 'walk me through the workflow' for a step-by-step tour, or ask about any component."
    )
    return {
        "spoken_summary": spoken,
        "visible_summary": spoken,
        "stages": [
            {"step": s["step"], "title": s["title"], "route": s["route"], "route_label": s["route_label"]}
            for s in WALKTHROUGH_STAGES
        ],
        "who_it_is_for": [
            "Network Operations Engineers (NOC / NRE)",
            "GPU Cluster & RDMA Fabric Infrastructure Teams",
            "Site Reliability Engineers (SREs)",
        ],
        "current_page": current_page,
    }


def explain_stage(stage: Dict[str, Any], *, is_interruption: bool = False) -> Dict[str, Any]:
    prefix = f"Step {stage['step']} of {len(WALKTHROUGH_STAGES)} — {stage['title']}: "
    if is_interruption:
        prefix = f"About {stage['title']} (Step {stage['step']} of {len(WALKTHROUGH_STAGES)}): "
    next_hint = (
        " Say 'next step' to continue the walkthrough."
        if stage["step"] < len(WALKTHROUGH_STAGES)
        else " That completes the 12-stage NetResolve AI lifecycle."
    )
    spoken = f"{prefix}{stage['summary']} {stage['details']}{next_hint}"
    return {
        "spoken_summary": spoken,
        "visible_summary": spoken,
        "stage": stage,
        "total_steps": len(WALKTHROUGH_STAGES),
        "navigate_to": stage["route"],
    }
