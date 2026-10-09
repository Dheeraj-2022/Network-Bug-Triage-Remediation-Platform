"""
Pydantic schemas for the Network Bug Triage & Remediation Platform API.

Defines request and response data contracts for:
- System status
- Telemetry events & injection
- Triage decisions & audit logging
- AI multi-agent incident management & approval
- ML model training & state reset
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Status & Health Schemas
# ---------------------------------------------------------------------------
class ModelStatus(BaseModel):
    trained: bool = False
    message: str = "Not trained yet"


class StatusResponse(BaseModel):
    total_events: int = 0
    total_decisions: int = 0
    remediations: int = 0
    model_trained: bool = False
    model_status: Union[ModelStatus, Dict[str, Any]]
    ai_incidents: int = 0


# ---------------------------------------------------------------------------
# Telemetry Event Schemas
# ---------------------------------------------------------------------------
class ProcessEventRequest(BaseModel):
    event_id: Optional[str] = None
    host: Optional[str] = "custom-host"
    ts: Optional[str] = None
    ifaces: Optional[Dict[str, Any]] = Field(default_factory=dict)
    rdma: Optional[Dict[str, Any]] = Field(default_factory=dict)
    dmesg_tail: Optional[str] = ""
    sample_packets: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class InjectRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=100, description="Number of events to inject (1-100)")
    inject_errors: bool = Field(default=True, description="Whether to inject simulated faults")


# ---------------------------------------------------------------------------
# Triage Decision Schemas
# ---------------------------------------------------------------------------
class AIDecisionSummary(BaseModel):
    incident_id: Optional[str] = None
    llm_backend: Optional[str] = None
    fault_domain: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    ai_playbook: Optional[str] = None
    risk: Optional[str] = None
    status: Optional[str] = None
    context_sources: Optional[List[Any]] = Field(default_factory=list)


class DecisionResponse(BaseModel):
    ts: str
    host: Optional[str] = None
    event_id: Optional[str] = None
    rule_action: Optional[str] = None
    rule_reason: Optional[str] = None
    log_class: Optional[str] = None
    ml_priority: Optional[float] = None
    ml_localization: Optional[str] = None
    remediate: bool = False
    playbook: Optional[str] = None
    ai: Optional[Union[AIDecisionSummary, Dict[str, Any]]] = None

    model_config = ConfigDict(extra="allow")


class InjectResponse(BaseModel):
    injected: int
    decisions: List[DecisionResponse]


class LoadSampleEventsResponse(BaseModel):
    loaded: int
    decisions: List[DecisionResponse]


# ---------------------------------------------------------------------------
# Remediation Audit Log Schemas
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    ts: str
    event_id: Optional[str] = None
    host: Optional[str] = None
    playbook: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Multi-Agent Schemas
# ---------------------------------------------------------------------------
class AIStatusResponse(BaseModel):
    enabled: bool
    uses_llm: Optional[bool] = None
    vertex_model: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class AIIncidentSummary(BaseModel):
    incident_id: Optional[str] = None
    ts: Optional[str] = None
    host: Optional[str] = None
    event_id: Optional[str] = None
    llm_backend: Optional[str] = None
    fault_domain: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    playbook: Optional[str] = None
    risk: Optional[str] = None
    status: Optional[str] = None
    requires_human_approval: Optional[bool] = None
    context_sources: Optional[List[Any]] = Field(default_factory=list)


class AIApproveRequest(BaseModel):
    incident_id: str
    approved: bool = True


class AIApproveResponse(BaseModel):
    ok: bool
    status: str
    incident_id: str
    validation: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Control & Maintenance Schemas
# ---------------------------------------------------------------------------
class TrainResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class ClearResponse(BaseModel):
    ok: bool = True
