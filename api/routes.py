"""
FastAPI route definitions for Network Bug Triage & Remediation Platform.
Exposes all /api/* endpoints matching the existing platform contracts.
"""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from api.service import service
from schemas import (
    AIApproveRequest,
    AIApproveResponse,
    AIIncidentSummary,
    AuditLogEntry,
    ClearResponse,
    DecisionResponse,
    InjectRequest,
    InjectResponse,
    LoadSampleEventsResponse,
    ProcessEventRequest,
    StatusResponse,
    TrainResponse,
)

router = APIRouter(tags=["Triage API"])


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
    event_dict = payload.model_dump()
    result = await asyncio.to_thread(service.process_single, event_dict)
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
    data, code = await asyncio.to_thread(service.approve_ai_incident, payload.incident_id, payload.approved)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


# ---------------------------------------------------------------------------
# Model Training & Management Endpoints
# ---------------------------------------------------------------------------
@router.post("/train", response_model=TrainResponse, summary="Trigger ML model training")
async def train_model():
    """Trigger retraining of the XGBoost triage classifier."""
    data, code = await asyncio.to_thread(service.train_model)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@router.post("/clear", response_model=ClearResponse, summary="Clear in-memory state")
async def clear_all():
    """Reset all in-memory events, decisions, audit entries, and AI incidents."""
    return service.clear()
