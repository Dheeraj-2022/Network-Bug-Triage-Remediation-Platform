"""
FastAPI route definitions for Network Bug Triage & Remediation Platform.
Exposes all /api/* endpoints matching the existing platform contracts.
"""

import asyncio
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse

from api.auth import api_key_required, require_api_key
from api.service import service
from schemas import (
    dump_model,
    AIApproveRequest,
    AIApproveResponse,
    AIIncidentSummary,
    AuditLogEntry,
    ClearResponse,
    DecisionResponse,
    DemoRunRequest,
    InjectRequest,
    InjectResponse,
    LoadSampleEventsResponse,
    ProcessEventRequest,
    RemediationDecisionRequest,
    StatusResponse,
    TrainResponse,
)

router = APIRouter(tags=["Triage API"], dependencies=[Depends(require_api_key)])
public_router = APIRouter(tags=["Auth"])

import pydantic
_PYDANTIC_V2 = int(pydantic.__version__.split(".", 1)[0]) >= 2
def _path_param(pattern: str):
    return Path(pattern=pattern) if _PYDANTIC_V2 else Path(regex=pattern)

PROPOSAL_ID_PATH = _path_param(r"^rem-[0-9a-f]{12}$")
TOPOLOGY_ID_PATH = _path_param(r"^[A-Za-z0-9_.-]{1,64}$")


@public_router.get("/auth", summary="Report whether an API key is required")
async def auth_info():
    """Public: tells the UI whether to ask the operator for an API key. Never returns the key."""
    return {
        "api_key_required": api_key_required(),
        "remediation_mode": service.policy.mode,
        "note": ("X-API-Key is a shared secret, not per-user auth. Approver names are self-asserted."
                 if api_key_required() else
                 "No API key configured: the API is unauthenticated. Keep it bound to localhost."),
    }


# ---------------------------------------------------------------------------
# Status & Monitoring Endpoints
# ---------------------------------------------------------------------------
@router.get("/status", response_model=StatusResponse, summary="Get system status & KPI summary")
async def get_status():
    """Returns overview statistics: total events, decisions, remediations, and ML/AI status."""
    return service.get_status()


# ---------------------------------------------------------------------------
# Telemetry Event Endpoints
# ---------------------------------------------------------------------------
@router.get("/events", response_model=List[Dict[str, Any]], summary="Get recent telemetry events")
async def get_events(limit: int = 50):
    """Retrieve the last N telemetry events ingested into the platform."""
    return service.get_events(limit=limit)


@router.post("/inject", response_model=InjectResponse, summary="Inject synthetic telemetry events")
async def inject_events(payload: Optional[InjectRequest] = None):
    """
    Generate and ingest synthetic host events with optional simulated faults,
    executing the full rule + ML + AI triage pipeline.
    """
    req = payload or InjectRequest()
    result = await asyncio.to_thread(service.inject_events, req.count, req.inject_errors)
    return result


@router.post("/process", response_model=DecisionResponse, summary="Process a single custom event")
async def process_single_event(payload: ProcessEventRequest):
    """Run the triage and remediation pipeline on a single custom telemetry event."""
    event_dict = dump_model(payload)
    result = await asyncio.to_thread(service.process_single, event_dict, True)
    return result


@router.post("/load_sample_events", response_model=LoadSampleEventsResponse, summary="Load sample event fixtures")
async def load_sample_events():
    """Load pre-recorded telemetry fixtures from data/sample_events.json and triage them."""
    data, code = await asyncio.to_thread(service.load_sample_events)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


# ---------------------------------------------------------------------------
# Triage Decisions & Audit Log Endpoints
# ---------------------------------------------------------------------------
@router.get("/decisions", response_model=List[DecisionResponse], summary="Get recent triage decisions")
async def get_decisions(limit: int = 50):
    """Retrieve the most recent triage decisions."""
    return service.get_decisions(limit=limit)


@router.get("/audit", response_model=List[AuditLogEntry], summary="Get remediation audit log")
async def get_audit(limit: int = 50):
    """Retrieve recent remediation audit entries (triggered playbooks, hosts, status)."""
    return service.get_audit(limit=limit)


# ---------------------------------------------------------------------------
# AI Multi-Agent Endpoints
# ---------------------------------------------------------------------------
@router.get("/ai/status", summary="Get AI multi-agent subsystem status")
async def get_ai_status():
    """Report status of the multi-agent reasoning layer, LLM backend, retrieval, and memory."""
    data, code = service.get_ai_status()
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@router.get("/ai/incidents", response_model=List[AIIncidentSummary], summary="List AI triage incidents")
async def get_ai_incidents(limit: int = 50):
    """Return recent multi-agent reasoning incidents with root-cause analysis and remediation proposals."""
    return service.get_ai_incidents(limit=limit)


@router.get("/ai/incident/{incident_id}", summary="Get detailed AI incident trace")
async def get_ai_incident_detail(incident_id: str):
    """Retrieve full trace, reasoning steps, and context sources for a specific incident."""
    incident = service.get_ai_incident_detail(incident_id)
    if not incident:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "incident not found"})
    return incident


@router.post("/ai/approve", response_model=AIApproveResponse, summary="Human approval gate for AI remediation")
async def approve_ai_incident(payload: AIApproveRequest):
    """
    Approve or reject a remediation plan proposed by the AI multi-agent orchestrator.
    If approved, optionally resumes execution and validation.
    """
    data, code = await asyncio.to_thread(
        service.approve_ai_incident, payload.incident_id, payload.approved, payload.approver, payload.preview_digest
    )
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


# ---------------------------------------------------------------------------
# Shared remediation policy (every remediation path goes through these)
# ---------------------------------------------------------------------------
@router.get("/remediations", summary="List remediation proposals")
async def list_remediations(limit: int = 50, scenario_id: Optional[str] = None):
    return await asyncio.to_thread(service.list_remediations, limit, scenario_id)


@router.get("/remediations/audit", summary="Persistent remediation audit trail")
async def remediation_audit(limit: int = 100, scenario_id: Optional[str] = None):
    return await asyncio.to_thread(service.get_remediation_audit, limit, scenario_id)


@router.get("/remediations/{proposal_id}", summary="Get one proposal with preview, decision, execution, post-check")
async def get_remediation(proposal_id: str = PROPOSAL_ID_PATH):
    p = await asyncio.to_thread(service.get_remediation, proposal_id)
    if p is None:
        return JSONResponse(status_code=404, content={"error": "proposal not found"})
    return p


@router.post("/remediations/{proposal_id}/decision", summary="Approve or reject a previewed remediation")
async def decide_remediation(payload: RemediationDecisionRequest, proposal_id: str = PROPOSAL_ID_PATH):
    """Approval executes in the mode bound at preview time (simulate by default), then runs the post-check.
    Duplicate, stale or changed-preview decisions return 409."""
    data, code = await asyncio.to_thread(
        service.decide_remediation, proposal_id, payload.approved, payload.approver,
        payload.preview_digest, payload.reason)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@router.post("/remediations/{proposal_id}/verify", summary="Re-run the post-check with available telemetry")
async def verify_remediation(proposal_id: str = PROPOSAL_ID_PATH):
    data, code = await asyncio.to_thread(service.verify_remediation, proposal_id)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


# ---------------------------------------------------------------------------
# Deterministic demo & topology
# ---------------------------------------------------------------------------
@router.get("/demo/mtu-two-host", summary="Current state of the two-host MTU demo (SIMULATED)")
async def get_demo():
    return await asyncio.to_thread(service.get_demo)


@router.post("/demo/mtu-two-host/load", summary="Reset and replay the two-host MTU demo (SIMULATED)")
async def load_demo(payload: Optional[DemoRunRequest] = None):
    """Removes only demo-scoped records, then replays the fixture through the real triage pipeline."""
    req = payload or DemoRunRequest()
    data, code = await asyncio.to_thread(service.run_demo, req.post_check)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@router.post("/demo/mtu-two-host/reset", summary="Remove only the demo's records")
async def reset_demo():
    return await asyncio.to_thread(service.reset_demo)


@router.get("/topology/{topology_id}", summary="Topology nodes, links and paths")
async def get_topology(topology_id: str = TOPOLOGY_ID_PATH):
    view = service.policy.registry.view(topology_id)
    if view is None:
        return JSONResponse(status_code=404, content={"error": "topology not found"})
    return view


# ---------------------------------------------------------------------------
# Model Training & Management Endpoints
# ---------------------------------------------------------------------------
@router.post("/train", response_model=TrainResponse, summary="Trigger ML model training")
async def train_model():
    """Retrain the host triage XGBoost model (synthetic data unless trained via the CLI with --events)."""
    data, code = await asyncio.to_thread(service.train_model)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@router.get("/models", summary="Trained model status, metrics and caveats")
async def get_models():
    return await asyncio.to_thread(service.get_models)


@router.post("/clear", response_model=ClearResponse, summary="Clear in-memory state")
async def clear_all():
    """Reset all in-memory events, decisions, audit entries, and AI incidents."""
    return service.clear()
