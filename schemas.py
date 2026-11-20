"""
Pydantic schemas for the Network Bug Triage & Remediation Platform API.

Defines request and response data contracts for:
- System status
- Telemetry events & injection
- Triage decisions & audit logging
- AI multi-agent incident management & approval
<<<<<<< HEAD
- Shared remediation policy & deterministic demo
- Secure voice-first operations assistant
- ML model training & state reset

Compatible with both Pydantic v1 and Pydantic v2.
"""

from typing import Any, Dict, List, Literal, Optional, Union
import pydantic
from pydantic import BaseModel, Field

_PYDANTIC_V2 = int(pydantic.__version__.split(".", 1)[0]) >= 2
if _PYDANTIC_V2:
    from pydantic import ConfigDict


def _pattern_field(pattern: str, **kwargs: Any) -> Any:
    if _PYDANTIC_V2:
        return Field(pattern=pattern, **kwargs)
    return Field(regex=pattern, **kwargs)


def dump_model(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()

=======
- ML model training & state reset
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6

HOST_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$"
APPROVER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$"


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
    event_id: Optional[str] = Field(default=None, max_length=128)
<<<<<<< HEAD
    host: Optional[str] = _pattern_field(HOST_PATTERN, default="custom-host")
=======
    host: Optional[str] = Field(default="custom-host", pattern=HOST_PATTERN)
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
    ts: Optional[str] = Field(default=None, max_length=64)
    ifaces: Optional[Dict[str, Any]] = Field(default_factory=dict)
    rdma: Optional[Dict[str, Any]] = Field(default_factory=dict)
    dmesg_tail: Optional[str] = Field(default="", max_length=20000)
    sample_packets: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

<<<<<<< HEAD
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"
=======
    model_config = ConfigDict(extra="allow")
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6


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
    simulated: bool = False
    scenario_id: Optional[str] = None
    remediation_id: Optional[str] = None
    remediation: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None

<<<<<<< HEAD
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"
=======
    model_config = ConfigDict(extra="allow")
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6


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
    remediation_id: Optional[str] = None
    mode: Optional[str] = None
    scenario_id: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Multi-Agent Schemas
# ---------------------------------------------------------------------------
class AIStatusResponse(BaseModel):
    enabled: bool
    uses_llm: Optional[bool] = None
    vertex_model: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None

<<<<<<< HEAD
    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"
=======
    model_config = ConfigDict(extra="allow")
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6


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
    remediation_id: Optional[str] = None
    simulated: bool = False


class AIApproveRequest(BaseModel):
    incident_id: str = Field(max_length=200)
    approved: bool = True
<<<<<<< HEAD
    approver: str = _pattern_field(APPROVER_PATTERN, default="api-user")
=======
    approver: str = Field(default="api-user", pattern=APPROVER_PATTERN)
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
    preview_digest: Optional[str] = Field(default=None, max_length=64)


class AIApproveResponse(BaseModel):
    ok: bool
    status: str
    incident_id: str
    remediation_id: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Shared remediation policy & demo
# ---------------------------------------------------------------------------
class RemediationDecisionRequest(BaseModel):
    approved: bool
<<<<<<< HEAD
    approver: str = _pattern_field(APPROVER_PATTERN, description="Name of the person deciding (self-asserted)")
=======
    approver: str = Field(pattern=APPROVER_PATTERN, description="Name of the person deciding (self-asserted)")
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
    preview_digest: Optional[str] = Field(default=None, max_length=64,
                                          description="Digest of the preview that was reviewed")
    reason: Optional[str] = Field(default=None, max_length=500)


class DemoRunRequest(BaseModel):
    post_check: Literal["pass", "fail", "inconclusive"] = "pass"


# ---------------------------------------------------------------------------
<<<<<<< HEAD
# Secure Voice Operations Assistant Schemas
# ---------------------------------------------------------------------------
class VoiceDemoSessionRequest(BaseModel):
    profile: Literal["viewer-gpu", "operator-gpu", "operator-lab", "senior-approver"] = "operator-gpu"


class VoiceQueryRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=1000)
    input_mode: Literal["voice", "text"] = "voice"
    page: int = Field(default=1, ge=1, le=50)
    page_size: int = Field(default=5, ge=1, le=20)
    post_check: Optional[Literal["pass", "fail", "inconclusive"]] = None
    session_id: Optional[str] = Field(default=None, max_length=64)
    current_page: Optional[str] = Field(default=None, max_length=64)


class VoiceConfirmRequest(BaseModel):
    confirmation_id: str = Field(min_length=4, max_length=64)
    confirm: bool
    confirmation_phrase: Optional[str] = Field(default=None, max_length=200)
    step_up_code: Optional[str] = Field(default=None, max_length=64)
    second_approver_token: Optional[str] = Field(default=None, max_length=256)
    reason: Optional[str] = Field(default=None, max_length=500)
    session_id: Optional[str] = Field(default=None, max_length=64)


class VoiceWalkthroughRequest(BaseModel):
    transcript: Optional[str] = Field(default=None, max_length=1000)
    step: Optional[int] = Field(default=None, ge=1, le=12)
    current_page: Optional[str] = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
=======
>>>>>>> ff89564813fe8c100cd1118813d53af4264c93d6
# Control & Maintenance Schemas
# ---------------------------------------------------------------------------
class TrainResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class ClearResponse(BaseModel):
    ok: bool = True
