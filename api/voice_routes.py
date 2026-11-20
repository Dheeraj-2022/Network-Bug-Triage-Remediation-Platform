"""
FastAPI routes for the secure conversational voice-first operations agent.

Security boundaries:
- GET /api/voice/config is public and returns non-secret capabilities & privacy notice.
- POST /api/voice/walkthrough is public and provides an anonymous-safe introductory
  walkthrough of NetResolve AI without exposing any protected infrastructure data.
- POST /api/voice/demo-session issues ephemeral in-memory demo tokens ONLY when
  configured voice users (NBT_VOICE_USERS_JSON / NBT_VOICE_USERS_FILE) are absent.
- Every operational endpoint (/me, /query, /confirm, /audit, /conversation) requires
  a valid backend-authenticated voice token (X-Voice-Token or Authorization: Bearer)
  and enforces role + per-host scope on the server.
- All endpoints also respect NBT_API_KEY via require_api_key when configured.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse

from api.auth import require_api_key
from api.service import service
from controller.voice import VoicePrincipal, get_voice_assistant
from schemas import (
    VoiceConfirmRequest,
    VoiceDemoSessionRequest,
    VoiceQueryRequest,
    VoiceWalkthroughRequest,
)

voice_public_router = APIRouter(prefix="/voice", tags=["Voice Assistant"])
voice_router = APIRouter(prefix="/voice", tags=["Voice Assistant"], dependencies=[Depends(require_api_key)])


def _extract_voice_token(
    x_voice_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    return x_voice_token or authorization


def require_voice_principal(
    token: Optional[str] = Depends(_extract_voice_token),
) -> VoicePrincipal:
    assistant = get_voice_assistant(service)
    principal = assistant.auth.authenticate(token)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid voice authentication token (X-Voice-Token or Authorization: Bearer).",
        )
    return principal


@voice_public_router.get("/config", summary="Public voice assistant capabilities and privacy notice")
async def voice_config():
    assistant = get_voice_assistant(service)
    return assistant.config_summary()


@voice_public_router.post("/walkthrough", summary="Anonymous-safe NetResolve AI application walkthrough")
async def voice_walkthrough(payload: Optional[VoiceWalkthroughRequest] = None):
    assistant = get_voice_assistant(service)
    req = payload or VoiceWalkthroughRequest()
    return await asyncio.to_thread(
        assistant.public_walkthrough,
        transcript=req.transcript,
        step=req.step,
        current_page=req.current_page,
    )


@voice_router.post("/demo-session", summary="Create an ephemeral local demo voice session token")
async def create_voice_demo_session(payload: VoiceDemoSessionRequest):
    assistant = get_voice_assistant(service)
    data, code = assistant.auth.create_demo_session(payload.profile)
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@voice_router.get("/me", summary="Return authenticated voice principal and authorized host scope")
async def voice_me(principal: VoicePrincipal = Depends(require_voice_principal)):
    return {"principal": principal.public_view()}


@voice_router.post("/query", summary="Submit a voice transcript or conversational text command")
async def voice_query(
    payload: VoiceQueryRequest,
    principal: VoicePrincipal = Depends(require_voice_principal),
):
    assistant = get_voice_assistant(service)
    data, code = await asyncio.to_thread(
        assistant.handle_query,
        principal,
        payload.transcript,
        input_mode=payload.input_mode,
        page=payload.page,
        page_size=payload.page_size,
        post_check=payload.post_check,
        session_id=payload.session_id,
        current_page=payload.current_page,
    )
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@voice_router.post("/confirm", summary="Explicitly confirm or cancel a pending state-changing voice operation")
async def voice_confirm(
    payload: VoiceConfirmRequest,
    principal: VoicePrincipal = Depends(require_voice_principal),
):
    assistant = get_voice_assistant(service)
    data, code = await asyncio.to_thread(
        assistant.handle_confirm,
        principal,
        payload.confirmation_id,
        confirm=payload.confirm,
        confirmation_phrase=payload.confirmation_phrase,
        step_up_code=payload.step_up_code,
        second_approver_token=payload.second_approver_token,
        reason=payload.reason,
        session_id=payload.session_id,
    )
    if code != 200:
        return JSONResponse(status_code=code, content=data)
    return data


@voice_router.get("/conversation", summary="Get current user's isolated conversation history and context")
async def voice_conversation(
    session_id: Optional[str] = None,
    principal: VoicePrincipal = Depends(require_voice_principal),
):
    assistant = get_voice_assistant(service)
    return await asyncio.to_thread(assistant.get_conversation, principal, session_id)


@voice_router.post("/conversation/clear", summary="Clear current user's conversation history and context")
async def voice_conversation_clear(
    session_id: Optional[str] = None,
    principal: VoicePrincipal = Depends(require_voice_principal),
):
    assistant = get_voice_assistant(service)
    return await asyncio.to_thread(assistant.clear_conversation, principal, session_id)


@voice_router.get("/audit", summary="List redacted voice assistant audit entries")
async def voice_audit(
    limit: int = 50,
    principal: VoicePrincipal = Depends(require_voice_principal),
):
    assistant = get_voice_assistant(service)
    return await asyncio.to_thread(assistant.list_audit, principal, limit)
