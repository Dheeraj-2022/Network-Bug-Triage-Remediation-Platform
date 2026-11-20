"""
Bounded, secure conversational voice-first operations assistant engine for NetResolve AI.

Combines:
- Strict security boundaries (backend auth, RBAC, per-host scope, secret redaction,
  prompt-injection defense, fail-closed forbidden rules, immutable audit log).
- Bounded ConversationalOpsAgent (reusing Vertex Gemini via LLMClient when online
  with honest deterministic offline fallback).
- Per-user isolated ConversationStore (multi-turn context, pronoun resolution,
  guided 12-stage application walkthrough).
- Multi-step backend incident investigation (telemetry, MTU, RDMA, kernel logs,
  rules, ML triage, topology intent, evidence, change correlation, AI RCA,
  and RemediationPolicy proposal discovery).
- Human-approved remediation workflow exclusively through RemediationPolicy
  with exact readback, digest binding, expiry, step-up / second-approver support,
  and deterministic post-remediation verification.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from controller.demo_scenarios import MTU_SCENARIO_ID
from controller.voice.agent import (
    ALL_ALLOWED_INTENTS,
    ConversationalOpsAgent,
    voice_allow_ansible,
)
from controller.voice.audit import VoiceAuditStore
from controller.voice.auth import VoiceAuthManager, VoicePrincipal
from controller.voice.conversation import ConversationState, ConversationStore
from controller.voice.intents import (
    STATE_CHANGING_INTENTS,
    ParsedIntent,
    is_explicit_confirmation,
)
from controller.voice.knowledge import (
    WALKTHROUGH_STAGES,
    build_app_overview,
    explain_stage,
    get_walkthrough_stage,
    match_architecture_topic,
)
from controller.voice.security import (
    detect_prompt_injection,
    redact_obj,
    redact_secrets,
    sanitize_retrieved_text,
)

CONFIRMATION_TTL_SECONDS = 120
STALE_TELEMETRY_SECONDS = 3600


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_stale(ts: Any, simulated: bool = False) -> bool:
    if simulated:
        return False
    dt = _parse_ts(ts)
    if dt is None:
        return True
    age = (datetime.now(timezone.utc) - dt).total_seconds()
    return age > STALE_TELEMETRY_SECONDS


class VoiceAssistant:
    def __init__(
        self,
        service: Any,
        auth: Optional[VoiceAuthManager] = None,
        audit: Optional[VoiceAuditStore] = None,
        confirmation_ttl_s: int = CONFIRMATION_TTL_SECONDS,
        llm_client: Any = None,
    ):
        self.service = service
        self.auth = auth or VoiceAuthManager()
        self.audit = audit or VoiceAuditStore()
        self.confirmation_ttl_s = confirmation_ttl_s
        self.conversations = ConversationStore()
        self.agent = ConversationalOpsAgent(llm_client=llm_client)
        self._lock = Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Config & Public Walkthrough (Anonymous-Safe)
    # ------------------------------------------------------------------
    def config_summary(self) -> Dict[str, Any]:
        base = self.auth.config_summary()
        llm_info = self.agent.llm_status()
        base.update({
            "llm_intent_mode": llm_info["mode"],
            "llm_backend": llm_info["backend"],
            "uses_llm": llm_info["uses_llm"],
            "remediation_mode": getattr(self.service.policy, "mode", "simulate"),
            "voice_allow_ansible": voice_allow_ansible(),
            "walkthrough_steps": len(WALKTHROUGH_STAGES),
        })
        return base

    def public_walkthrough(
        self,
        *,
        transcript: Optional[str] = None,
        step: Optional[int] = None,
        current_page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Anonymous-safe introductory walkthrough. Never exposes infrastructure data."""
        raw = redact_secrets(transcript or "").strip()
        if raw and detect_prompt_injection(raw):
            return {
                "status": "refused",
                "spoken_summary": "Request refused due to security policy.",
                "visible_summary": "Refused: untrusted prompt-injection attempt detected.",
                "injection_flagged": True,
                "anonymous_mode": True,
            }
        if step is not None:
            stage = get_walkthrough_stage(step)
            res = explain_stage(stage)
            return {"status": "ok", "anonymous_mode": True, **res}
        if raw:
            topic = match_architecture_topic(raw)
            if topic:
                res = explain_stage(topic, is_interruption=True)
                return {"status": "ok", "anonymous_mode": True, **res}
        overview = build_app_overview(current_page=current_page)
        return {
            "status": "ok",
            "anonymous_mode": True,
            "note": "Authenticate with a voice session to inspect live/simulated hosts, incidents, or remediation proposals.",
            **overview,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _known_hosts(self) -> List[str]:
        hosts = set()
        reg = self.service.policy.registry
        for tid in reg.topology_ids():
            view = reg.view(tid) or {}
            for node in view.get("nodes", []):
                if node.get("kind") == "host" and node.get("name"):
                    hosts.add(node["name"])
        for ev in self.service.get_events(limit=200):
            if ev.get("host"):
                hosts.add(ev["host"])
        return sorted(hosts)

    def _authorized_hosts(self, principal: VoicePrincipal) -> List[str]:
        return [h for h in self._known_hosts() if principal.can_access_host(h)]

    def _paginate(self, items: List[Any], page: int, page_size: int) -> Tuple[List[Any], Dict[str, Any]]:
        size = max(1, min(int(page_size), 20))
        pg = max(1, int(page))
        total = len(items)
        start = (pg - 1) * size
        end = start + size
        return items[start:end], {
            "page": pg,
            "page_size": size,
            "total": total,
            "has_more": end < total,
        }

    def _update_context(
        self,
        state: Optional[ConversationState],
        *,
        transcript: str,
        spoken_summary: str,
        intent: Optional[str],
        status: str,
        host: Optional[str] = None,
        proposal_id: Optional[str] = None,
        incident_id: Optional[str] = None,
        event_id: Optional[str] = None,
        confirmation_id: Optional[str] = None,
        navigate_to: Optional[str] = None,
        stage: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if state is None:
            return None
        if host:
            state.selected_host = host
        if proposal_id:
            state.selected_proposal_id = proposal_id
        if incident_id:
            state.selected_incident_id = incident_id
        if event_id:
            state.selected_event_id = event_id
        if stage:
            state.investigation_stage = stage
        if topic:
            state.active_topic = topic
        if status == "confirmation_required" and confirmation_id:
            state.pending_confirmation_id = confirmation_id
        elif status in ("verified_resolved", "verification_failed", "verification_inconclusive", "cancelled", "expired"):
            if state.pending_confirmation_id == confirmation_id:
                state.pending_confirmation_id = None
        if transcript:
            state.add_turn("user", transcript, intent=intent, host=host, proposal_id=proposal_id)
        state.add_turn(
            "assistant",
            spoken_summary,
            intent=intent,
            status=status,
            host=host or state.selected_host,
            proposal_id=proposal_id or state.selected_proposal_id,
            navigate_to=navigate_to,
        )
        return state.public_context()

    def _audit_and_return(
        self,
        *,
        principal: VoicePrincipal,
        input_mode: str,
        transcript: str,
        parsed: Optional[ParsedIntent],
        authorized: bool,
        status: str,
        spoken_summary: str,
        visible_summary: str,
        target_host: Optional[str] = None,
        target_entity: Optional[str] = None,
        confirmation_id: Optional[str] = None,
        confirmation: Optional[Dict[str, Any]] = None,
        decision: Optional[str] = None,
        injection_flagged: bool = False,
        evidence_meta: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None,
        http_status: int = 200,
        conv_state: Optional[ConversationState] = None,
        navigate_to: Optional[str] = None,
        suggested_actions: Optional[List[str]] = None,
        ai_backend: Optional[str] = None,
        stage: Optional[str] = None,
        topic: Optional[str] = None,
        proposal_id: Optional[str] = None,
        incident_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int]:
        safe_transcript = redact_secrets(transcript)
        safe_spoken = redact_secrets(spoken_summary)
        safe_visible = redact_secrets(visible_summary)
        safe_data = redact_obj(data) if data is not None else None
        safe_confirmation = redact_obj(confirmation) if confirmation is not None else None
        safe_meta = redact_obj(evidence_meta or {})

        entry = self.audit.record(
            user_id=principal.user_id,
            role=principal.role,
            input_mode=input_mode,
            transcript=safe_transcript,
            intent=parsed.intent if parsed else None,
            target_host=target_host or (parsed.host if parsed else None),
            target_entity=target_entity,
            authorized=authorized,
            confirmation_id=confirmation_id,
            decision=decision,
            outcome=status,
            injection_flagged=injection_flagged,
            detail={
                "matched_rule": parsed.matched_rule if parsed else None,
                "forbidden_code": parsed.forbidden_code if parsed else None,
            },
        )
        ctx = self._update_context(
            conv_state,
            transcript=safe_transcript,
            spoken_summary=safe_spoken,
            intent=parsed.intent if parsed else None,
            status=status,
            host=target_host if authorized else None,
            proposal_id=proposal_id or (target_entity if str(target_entity or "").startswith("rem-") else None),
            incident_id=incident_id,
            event_id=event_id,
            confirmation_id=confirmation_id,
            navigate_to=navigate_to,
            stage=stage,
            topic=topic,
        )
        llm_info = self.agent.llm_status()
        body: Dict[str, Any] = {
            "status": status,
            "recognized_transcript": safe_transcript,
            "interpreted": parsed.to_dict() if parsed else None,
            "spoken_summary": safe_spoken,
            "visible_summary": safe_visible,
            "evidence_meta": safe_meta,
            "data": safe_data,
            "pagination": pagination,
            "confirmation": safe_confirmation,
            "injection_flagged": injection_flagged,
            "audit_seq": entry["seq"],
            "ts": entry["ts"],
            "principal": principal.public_view(),
            "conversation_context": ctx,
            "navigate_to": navigate_to,
            "suggested_actions": suggested_actions or [],
            "ai_backend": ai_backend or llm_info["backend"],
            "uses_llm": llm_info["uses_llm"],
        }
        return body, http_status

    # ------------------------------------------------------------------
    # Main query entrypoint
    # ------------------------------------------------------------------
    def handle_query(
        self,
        principal: VoicePrincipal,
        transcript: str,
        *,
        input_mode: str = "voice",
        page: int = 1,
        page_size: int = 5,
        post_check: Optional[str] = None,
        session_id: Optional[str] = None,
        current_page: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int]:
        redacted_transcript = redact_secrets(transcript)
        conv_state = self.conversations.get(principal.user_id, session_id)
        if current_page:
            conv_state.current_page = current_page

        # 1. Prompt-injection / policy-bypass check on untrusted transcript.
        inj_hits = detect_prompt_injection(redacted_transcript)
        if inj_hits:
            msg = (
                "Refused: the request appears to attempt a policy bypass, secret disclosure, "
                "or unauthorized execution. Only allowlisted platform operations are supported."
            )
            return self._audit_and_return(
                principal=principal,
                input_mode=input_mode,
                transcript=redacted_transcript,
                parsed=ParsedIntent(intent=None, forbidden_code="prompt_injection", matched_rule=",".join(inj_hits)),
                authorized=False,
                status="refused",
                spoken_summary="Request refused due to security policy.",
                visible_summary=msg,
                injection_flagged=True,
                http_status=403,
                conv_state=conv_state,
            )

        # 1b. If the user has an active pending confirmation in this session and speaks an
        #     explicit confirmation or cancellation phrase ("yes confirm" / "cancel"),
        #     route it through handle_confirm directly for natural multi-turn voice flow.
        if conv_state.pending_confirmation_id:
            with self._lock:
                pend = self._pending.get(conv_state.pending_confirmation_id)
            if pend and not pend.get("consumed") and pend.get("user_id") == principal.user_id:
                phrase_ok, _ = is_explicit_confirmation(redacted_transcript)
                if phrase_ok is not None:
                    return self.handle_confirm(
                        principal,
                        conv_state.pending_confirmation_id,
                        confirm=bool(phrase_ok),
                        confirmation_phrase=redacted_transcript,
                        session_id=session_id,
                    )

        # 2. Plan into strict allowlisted intent (conversational + contextual + LLM/deterministic).
        parsed = self.agent.plan_intent(
            redacted_transcript,
            known_hosts=self._known_hosts(),
            state=conv_state,
        )

        if parsed.forbidden_code:
            return self._audit_and_return(
                principal=principal,
                input_mode=input_mode,
                transcript=redacted_transcript,
                parsed=parsed,
                authorized=False,
                status="refused",
                spoken_summary=parsed.forbidden_reason or "That operation is not permitted over voice.",
                visible_summary=parsed.forbidden_reason or "That operation is not permitted over voice.",
                http_status=403,
                conv_state=conv_state,
            )

        if parsed.broad_request or parsed.ambiguous or parsed.intent not in ALL_ALLOWED_INTENTS:
            msg = parsed.clarification or "Could you repeat or clarify which host and operation you want?"
            return self._audit_and_return(
                principal=principal,
                input_mode=input_mode,
                transcript=redacted_transcript,
                parsed=parsed,
                authorized=True,
                status="clarification_needed",
                spoken_summary=msg,
                visible_summary=msg,
                http_status=200,
                conv_state=conv_state,
                suggested_actions=[
                    "Is everything running smoothly?",
                    "Which host has the most serious issue?",
                    "Explain what NetResolve AI does",
                ],
            )

        # 3. Role-based authorization check for write / demo operations.
        if parsed.intent in (STATE_CHANGING_INTENTS | {"demo_load", "demo_reset"}) and not principal.can_write():
            msg = (
                f"Unauthorized: role '{principal.role}' is read-only and cannot perform '{parsed.intent}'."
            )
            return self._audit_and_return(
                principal=principal,
                input_mode=input_mode,
                transcript=redacted_transcript,
                parsed=parsed,
                authorized=False,
                status="unauthorized",
                spoken_summary="You do not have permission for that operation.",
                visible_summary=msg,
                http_status=403,
                conv_state=conv_state,
            )

        # 4. Per-host authorization check when a host is named.
        if parsed.host and not principal.can_access_host(parsed.host):
            msg = f"Unauthorized: host '{parsed.host}' is outside your authorized host scope."
            return self._audit_and_return(
                principal=principal,
                input_mode=input_mode,
                transcript=redacted_transcript,
                parsed=parsed,
                authorized=False,
                status="unauthorized",
                spoken_summary=f"You are not authorized to access {parsed.host}.",
                visible_summary=msg,
                target_host=parsed.host,
                http_status=403,
                conv_state=conv_state,
            )

        # 5. Dispatch strictly to allowlisted handler.
        handlers = {
            "app_overview": self._op_app_overview,
            "app_walkthrough": self._op_app_walkthrough,
            "platform_health": self._op_platform_health,
            "highest_priority_incident": self._op_highest_priority_incident,
            "investigate_host": self._op_investigate_host,
            "host_logs": self._op_host_logs,
            "plan_remediation": self._op_plan_remediation,
            "server_status": self._op_server_status,
            "recent_incidents": self._op_recent_incidents,
            "incident_evidence": self._op_incident_evidence,
            "server_topology": self._op_server_topology,
            "change_correlation": self._op_change_correlation,
            "drift_findings": self._op_drift_findings,
            "remediation_status": self._op_remediation_status,
            "verification_result": self._op_verification_result,
            "demo_load": self._op_demo_load,
            "demo_reset": self._op_demo_reset_request,
            "preview_remediation": self._op_preview_remediation,
            "approve_remediation": self._op_approve_remediation_request,
        }
        return handlers[parsed.intent](
            principal=principal,
            transcript=redacted_transcript,
            input_mode=input_mode,
            parsed=parsed,
            page=page,
            page_size=page_size,
            post_check=post_check,
            conv_state=conv_state,
        )

    # ------------------------------------------------------------------
    # New Conversational Operations Agent Handlers
    # ------------------------------------------------------------------
    def _op_app_overview(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        overview = build_app_overview(current_page=conv_state.current_page)
        conv_state.active_topic = "walkthrough"
        conv_state.walkthrough_step = 0
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=overview["spoken_summary"],
            visible_summary=overview["visible_summary"],
            evidence_meta={"sources": ["netresolve-architecture"], "simulated": False},
            data=overview,
            conv_state=conv_state,
            topic="walkthrough",
            suggested_actions=[
                "Walk me through the workflow step by step",
                "Is everything running smoothly?",
                "Load the MTU demo",
            ],
        )

    def _op_app_walkthrough(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        topic_step = parsed.extra.get("topic_step")
        if topic_step:
            stage = get_walkthrough_stage(int(topic_step))
            res = explain_stage(stage, is_interruption=bool(parsed.extra.get("is_interruption")))
        else:
            direction = parsed.extra.get("direction", "next")
            if direction == "prev":
                next_step = max(1, conv_state.walkthrough_step - 1)
            else:
                next_step = min(len(WALKTHROUGH_STAGES), conv_state.walkthrough_step + 1)
            conv_state.walkthrough_step = next_step
            stage = get_walkthrough_stage(next_step)
            res = explain_stage(stage)
        conv_state.active_topic = "walkthrough"
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=res["spoken_summary"],
            visible_summary=res["visible_summary"],
            evidence_meta={"sources": ["netresolve-walkthrough"], "simulated": False},
            data=res,
            conv_state=conv_state,
            navigate_to=res["navigate_to"],
            topic="walkthrough",
            suggested_actions=(
                ["Next step", "What is XGBoost doing here?", "Is everything running smoothly?"]
                if stage["step"] < len(WALKTHROUGH_STAGES)
                else ["Is everything running smoothly?", "Load the MTU demo"]
            ),
        )

    def _op_platform_health(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        sys_status = self.service.get_status()
        ai_status, _ = self.service.get_ai_status()
        auth_hosts = self._authorized_hosts(principal)
        events = [e for e in self.service.get_events(limit=200) if principal.can_access_host(e.get("host"))]
        decisions = [d for d in self.service.get_decisions(limit=200) if principal.can_access_host(d.get("host"))]
        proposals = [p for p in self.service.list_remediations(limit=50) if principal.can_access_host(p.get("host"))]

        healthy_hosts: List[str] = []
        faulty_hosts: List[Dict[str, Any]] = []
        stale_hosts: List[str] = []
        no_telemetry_hosts: List[str] = []

        for h in auth_hosts:
            he = [e for e in events if e.get("host") == h]
            hd = [d for d in decisions if d.get("host") == h]
            if not he:
                no_telemetry_hosts.append(h)
                continue
            last_ev = he[-1]
            last_dec = hd[-1] if hd else None
            sim = bool(last_ev.get("simulated"))
            stale = _is_stale(last_ev.get("ts"), simulated=sim)
            dom = (((last_dec or {}).get("evidence") or {}).get("inference") or {}).get("fault_domain")
            rem = (last_dec or {}).get("remediation") or {}
            is_resolved = rem.get("status") == "resolved"
            if dom and dom != "UNKNOWN" and not is_resolved:
                faulty_hosts.append({
                    "host": h,
                    "fault_domain": dom,
                    "remediation_status": rem.get("status"),
                    "simulated": sim,
                    "stale": stale,
                })
            elif stale:
                stale_hosts.append(h)
            else:
                healthy_hosts.append(h)

        pending_props = [p for p in proposals if p.get("status") == "pending_approval"]
        failed_ver = [p for p in proposals if p.get("status") == "verification_failed"]
        inconclusive_ver = [p for p in proposals if p.get("status") == "verification_inconclusive"]
        resolved_props = [p for p in proposals if p.get("status") == "resolved"]
        llm_info = self.agent.llm_status()

        parts = [f"Controller is reachable ({len(auth_hosts)} authorized host(s) in scope)."]
        if not events:
            parts.append("Telemetry pipeline has 0 ingested events in your scope, so infrastructure health cannot be confirmed as healthy.")
        else:
            if faulty_hosts:
                desc = ", ".join(
                    f"{fh['host']} ({fh['fault_domain']}{' simulated' if fh['simulated'] else ''})"
                    for fh in faulty_hosts[:3]
                )
                parts.append(f"Found {len(faulty_hosts)} host(s) with active faults: {desc}.")
            else:
                parts.append(f"{len(healthy_hosts)} host(s) show no active faults.")
            if stale_hosts:
                parts.append(f"{len(stale_hosts)} host(s) have stale telemetry ({', '.join(stale_hosts[:3])}).")
            if no_telemetry_hosts:
                parts.append(f"{len(no_telemetry_hosts)} registered host(s) have no telemetry samples yet.")
        if pending_props:
            parts.append(f"{len(pending_props)} remediation proposal(s) awaiting human approval.")
        if failed_ver:
            parts.append(f"{len(failed_ver)} remediation(s) failed post-check verification.")
        if inconclusive_ver:
            parts.append(f"{len(inconclusive_ver)} remediation(s) have inconclusive verification.")
        if not llm_info["uses_llm"]:
            parts.append("AI engine is running in offline deterministic heuristic fallback mode (Vertex Gemini unavailable).")
        else:
            parts.append(f"AI engine is active ({ai_status.get('llm_backend') or llm_info['backend']}).")

        baseline = " ".join(parts)
        data = {
            "controller_connected": True,
            "remediation_mode": self.service.policy.mode,
            "authorized_host_count": len(auth_hosts),
            "healthy_hosts": healthy_hosts,
            "faulty_hosts": faulty_hosts,
            "stale_hosts": stale_hosts,
            "no_telemetry_hosts": no_telemetry_hosts,
            "total_events_in_scope": len(events),
            "pending_approvals": len(pending_props),
            "verification_failed": len(failed_ver),
            "verification_inconclusive": len(inconclusive_ver),
            "verified_resolved": len(resolved_props),
            "model_trained": bool(sys_status.get("model_trained")),
            "ai_engine": {
                "enabled": bool(ai_status.get("enabled")),
                "uses_llm": llm_info["uses_llm"],
                "backend": ai_status.get("llm_backend") or llm_info["backend"],
            },
        }
        spoken, backend_used = self.agent.synthesize_response(
            intent="platform_health", transcript=transcript, deterministic_summary=baseline, structured_data=data
        )
        top_host = faulty_hosts[0]["host"] if faulty_hosts else None
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=spoken, visible_summary=baseline,
            target_host=top_host,
            evidence_meta={
                "entities": auth_hosts[:10],
                "sources": ["system-status", "telemetry", "triage-decisions", "remediation-policy"],
                "simulated": any(bool(e.get("simulated")) for e in events),
                "stale": bool(stale_hosts) or not events,
                "uncertain": not events,
            },
            data=data,
            conv_state=conv_state,
            navigate_to="overview",
            ai_backend=backend_used,
            topic="status",
            stage="triage",
            suggested_actions=(
                ["Which host has the most serious issue?", f"Investigate {top_host}"]
                if top_host else ["Load the MTU demo", "Explain what NetResolve AI does"]
            ),
        )

    def _rank_decisions(self, principal: VoicePrincipal) -> List[Dict[str, Any]]:
        decs = [
            d for d in reversed(self.service.get_decisions(limit=200))
            if principal.can_access_host(d.get("host"))
            and (d.get("remediate") or ((d.get("evidence") or {}).get("inference") or {}).get("fault_domain") not in (None, "UNKNOWN"))
        ]
        # Deduplicate to latest per host
        by_host: Dict[str, Dict[str, Any]] = {}
        for d in decs:
            h = d.get("host")
            if h and h not in by_host:
                by_host[h] = d
        conf_weight = {"high": 3.0, "medium": 2.0, "low": 1.0}
        def score(d: Dict[str, Any]) -> Tuple[int, float, float]:
            rem = d.get("remediation") or {}
            unresolved = 0 if rem.get("status") == "resolved" else 1
            pending = 1 if rem.get("status") == "pending_approval" else 0
            ev = d.get("evidence") or {}
            c_lvl = conf_weight.get((ev.get("confidence") or {}).get("level") or "low", 1.0)
            ml_p = float(d.get("ml_priority") or 0.0)
            return (unresolved * 2 + pending, c_lvl, ml_p)
        return sorted(by_host.values(), key=score, reverse=True)

    def _op_highest_priority_incident(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        ranked = self._rank_decisions(principal)
        if not ranked:
            msg = "There are currently no active incidents in your authorized host scope."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                evidence_meta={"missing": True}, data={"incidents": []},
                conv_state=conv_state, suggested_actions=["Load the MTU demo", "Is everything running smoothly?"],
            )
        top = ranked[0]
        host = top.get("host")
        ev = top.get("evidence") or {}
        inf = ev.get("inference") or {}
        conf = ev.get("confidence") or {}
        rem = top.get("remediation") or {}
        mtu_mismatches = [m for m in (ev.get("mtu_checks") or []) if m.get("status") == "mismatch"]
        mtu_note = ""
        if mtu_mismatches:
            m0 = mtu_mismatches[0]
            mtu_note = f" Interface {m0.get('iface')} has observed MTU {m0.get('observed')} vs expected {m0.get('expected')}."
        sim_tag = " (simulated)" if top.get("simulated") else ""
        baseline = (
            f"{host}{sim_tag} currently has the highest-priority incident: {inf.get('fault_domain', 'UNKNOWN')} "
            f"(evidence strength: {conf.get('level', 'low')}, remediation status: {rem.get('status') or 'none'}).{mtu_note}"
        )
        data = {
            "top_incident": {
                "host": host,
                "event_id": top.get("event_id"),
                "fault_domain": inf.get("fault_domain"),
                "confidence": conf.get("level"),
                "ml_priority": top.get("ml_priority"),
                "remediation_id": top.get("remediation_id"),
                "remediation_status": rem.get("status"),
                "simulated": bool(top.get("simulated")),
                "mtu_mismatches": mtu_mismatches,
            },
            "total_active_hosts": len(ranked),
        }
        spoken, backend_used = self.agent.synthesize_response(
            intent="highest_priority_incident", transcript=transcript, deterministic_summary=baseline, structured_data=data
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=spoken, visible_summary=baseline,
            target_host=host,
            target_entity=top.get("remediation_id") or top.get("event_id"),
            proposal_id=top.get("remediation_id"),
            event_id=top.get("event_id"),
            evidence_meta={
                "entities": [host],
                "timestamps": [top.get("ts")],
                "sources": ["triage-decisions", "deterministic-evidence"],
                "simulated": bool(top.get("simulated")),
            },
            data=data,
            conv_state=conv_state,
            navigate_to="incidents",
            ai_backend=backend_used,
            topic="investigation",
            stage="triage",
            suggested_actions=[
                f"Investigate {host}",
                "Show me the logs for that host",
                "Can you fix this issue?",
            ],
        )

    def _op_investigate_host(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        host = parsed.host
        if not host:
            ranked = self._rank_decisions(principal)
            if ranked:
                host = ranked[0].get("host")
        if not host:
            msg = "No host with an active incident was found in your authorized scope. Please specify an authorized host to investigate."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="clarification_needed", spoken_summary=msg, visible_summary=msg,
                conv_state=conv_state,
            )
        if not principal.can_access_host(host):
            msg = f"Unauthorized: host '{host}' is outside your authorized host scope."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized",
                spoken_summary=f"You are not authorized to investigate {host}.", visible_summary=msg,
                target_host=host, http_status=403, conv_state=conv_state,
            )

        # Multi-step backend investigation using existing NetResolve AI services
        host_events = [e for e in self.service.get_events(limit=200) if e.get("host") == host]
        host_decs = [d for d in self.service.get_decisions(limit=200) if d.get("host") == host]
        latest_ev = host_events[-1] if host_events else None
        latest_dec = host_decs[-1] if host_decs else None
        topo_host = self.service.policy.registry.host(host)
        topo_ifaces = self.service.policy.registry.interfaces(host) if topo_host else []

        if not latest_ev and not latest_dec:
            msg = (
                f"Insufficient evidence to diagnose {host}: no telemetry samples or triage decisions "
                "have been ingested for this host yet. Collect telemetry or run diagnostics first."
            )
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=host, evidence_meta={"entities": [host], "missing": True, "uncertain": True},
                data={"host": host, "insufficient_evidence": True, "topology_registered": topo_host is not None},
                conv_state=conv_state, stage="evidence", topic="investigation",
            )

        ev = (latest_dec or {}).get("evidence") or {}
        inf = ev.get("inference") or {}
        conf = ev.get("confidence") or {}
        loc = ev.get("localization") or {}
        mtu_checks = ev.get("mtu_checks") or []
        counters = ev.get("counters") or []
        scope = ev.get("scope") or {}

        # Sanitize logs & change correlations (prompt-injection defense)
        inj_any = False
        safe_logs = []
        for ln in (ev.get("log_lines") or [])[:6]:
            txt, inj = sanitize_retrieved_text(ln.get("text") or "")
            inj_any = inj_any or inj
            safe_logs.append({"line_no": ln.get("line_no"), "text": txt, "tags": ln.get("tags")})
        if not safe_logs and latest_ev and latest_ev.get("dmesg_tail"):
            for idx, line in enumerate(str(latest_ev.get("dmesg_tail")).splitlines()[:6], start=1):
                txt, inj = sanitize_retrieved_text(line)
                inj_any = inj_any or inj
                if txt:
                    safe_logs.append({"line_no": idx, "text": txt, "tags": []})

        safe_changes = []
        for ch in ((ev.get("change_correlation") or {}).get("items") or [])[:5]:
            s_txt, inj = sanitize_retrieved_text(ch.get("summary") or "")
            inj_any = inj_any or inj
            safe_changes.append({**ch, "summary": s_txt})

        # AI RCA detail (model-generated reasoning — kept distinct from deterministic facts)
        ai_meta = (latest_dec or {}).get("ai") or {}
        ai_inc_id = ai_meta.get("incident_id")
        ai_detail = self.service.get_ai_incident_detail(ai_inc_id) if ai_inc_id else None
        model_reasoning = None
        if ai_detail and ai_detail.get("rca"):
            rca_txt, inj_r = sanitize_retrieved_text(ai_detail["rca"].get("explanation") or ai_detail["rca"].get("root_cause") or "", max_len=400)
            inj_any = inj_any or inj_r
            model_reasoning = {
                "label": "model-generated (probabilistic)",
                "backend": ai_detail.get("llm_backend"),
                "root_cause": ai_detail["rca"].get("root_cause"),
                "confidence": ai_detail["rca"].get("confidence"),
                "explanation": rca_txt,
            }

        # Proposal check (without executing!)
        prop, _ = self._resolve_proposal(principal, host, (latest_dec or {}).get("remediation_id"))
        related_count = len([d for d in host_decs if d.get("remediate") or ((d.get("evidence") or {}).get("inference") or {}).get("fault_domain") not in (None, "UNKNOWN")])

        # Build concise, honest structured explanation
        domain = inf.get("fault_domain") or (latest_dec or {}).get("log_class") or "UNKNOWN"
        sim = bool((latest_ev or {}).get("simulated") or (latest_dec or {}).get("simulated"))
        stmt, inj_s = sanitize_retrieved_text(inf.get("statement") or "No deterministic root cause confirmed.")
        inj_any = inj_any or inj_s

        parts = [
            f"Investigation for {host}{' (simulated telemetry)' if sim else ''}:",
            f"Deterministic diagnosis: {domain} ({inf.get('status', 'undetermined')}, {conf.get('supporting_checks', 0)}/{conf.get('total_checks', 0)} checks passed).",
            stmt,
        ]
        mismatches = [m for m in mtu_checks if m.get("status") == "mismatch"]
        if mismatches:
            m0 = mismatches[0]
            parts.append(f"Observed MTU on {m0.get('iface')} is {m0.get('observed')} vs topology expected {m0.get('expected')}.")
        rdma = (latest_ev or {}).get("rdma") or {}
        if rdma.get("qp_errors"):
            parts.append(f"RDMA queue-pair errors observed: {rdma.get('qp_errors')}.")
        rel_changes = [c for c in safe_changes if c.get("relevance") == "relevant"]
        if rel_changes:
            parts.append(
                f"Correlated recent change {rel_changes[0].get('change_id')} on {rel_changes[0].get('entity')} "
                "(correlation only, not proof of causation)."
            )
        if prop and prop.get("status") == "pending_approval":
            prev = prop.get("preview") or {}
            parts.append(
                f"A validated remediation proposal ({prop['id']}) is ready: {prev.get('action')} in {prop.get('mode')} mode (risk: {prev.get('risk')}). "
                "Ask to preview or fix it to inspect the full execution plan."
            )
        elif prop:
            parts.append(f"Latest proposal {prop['id']} is currently {prop.get('status')}.")
        else:
            parts.append("No validated remediation proposal is currently pending for this host.")

        baseline = " ".join(parts)
        report = {
            "host": host,
            "simulated": sim,
            "started_ts": host_events[0].get("ts") if host_events else None,
            "latest_ts": (latest_ev or {}).get("ts"),
            "deterministic_facts": {
                "fault_domain": domain,
                "status": inf.get("status"),
                "statement": stmt,
                "evidence_strength": conf,
                "rule_action": (latest_dec or {}).get("rule_action"),
                "rule_reason": (latest_dec or {}).get("rule_reason"),
                "mtu_checks": mtu_checks,
                "counters": counters,
                "rdma": rdma,
                "ifaces": (latest_ev or {}).get("ifaces") or {},
                "log_lines": safe_logs,
                "topology_interfaces": [
                    {"name": i.get("name"), "intended_mtu": i.get("intended_mtu"), "driver": i.get("driver")}
                    for i in topo_ifaces
                ],
                "blast_radius": scope.get("blast_radius", []),
            },
            "change_correlations": {
                "note": "Correlation only — not proof of causation.",
                "items": safe_changes,
            },
            "probabilistic_signals": {
                "ml_priority": (latest_dec or {}).get("ml_priority"),
                "ml_localization": (latest_dec or {}).get("ml_localization"),
                "log_class": (latest_dec or {}).get("log_class"),
                "model_reasoning": model_reasoning,
            },
            "related_incident_count": related_count,
            "remediation_candidate": {
                "proposal_id": prop.get("id"),
                "status": prop.get("status"),
                "action": (prop.get("preview") or {}).get("action"),
                "mode": prop.get("mode"),
                "risk": (prop.get("preview") or {}).get("risk"),
            } if prop else None,
        }
        spoken, backend_used = self.agent.synthesize_response(
            intent="investigate_host", transcript=transcript, deterministic_summary=baseline, structured_data=report
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=spoken, visible_summary=baseline,
            target_host=host,
            target_entity=(loc.get("host") or {}).get("entity_id") or (latest_dec or {}).get("event_id"),
            proposal_id=prop.get("id") if prop else None,
            incident_id=ai_inc_id,
            event_id=(latest_dec or {}).get("event_id"),
            injection_flagged=inj_any,
            evidence_meta={
                "entities": [host],
                "timestamps": [(latest_ev or {}).get("ts")] if latest_ev else [],
                "sources": ["telemetry", "topology", "deterministic-evidence", "triage-decisions"],
                "simulated": sim,
                "uncertain": conf.get("level") == "low" or inf.get("status") != "confirmed",
            },
            data={"investigation": report},
            conv_state=conv_state,
            navigate_to="incidents",
            ai_backend=backend_used,
            topic="investigation",
            stage="diagnosis",
            suggested_actions=(
                ["Show me its logs", "Can you fix this issue?", f"Show topology for {host}"]
                if prop and prop.get("status") == "pending_approval"
                else ["Show me its logs", f"Show topology for {host}"]
            ),
        )

    def _op_host_logs(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        host = parsed.host or conv_state.selected_host
        if not host:
            msg = "Which authorized host's logs would you like to inspect? (For example, gpu-b.)"
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="clarification_needed", spoken_summary=msg, visible_summary=msg,
                conv_state=conv_state,
            )
        if not principal.can_access_host(host):
            msg = f"Unauthorized: host '{host}' is outside your authorized host scope."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized",
                spoken_summary=f"You are not authorized to view logs for {host}.", visible_summary=msg,
                target_host=host, http_status=403, conv_state=conv_state,
            )
        host_events = [e for e in self.service.get_events(limit=200) if e.get("host") == host]
        dec = self._find_latest_decision(principal, host, None)
        ev = (dec or {}).get("evidence") or {}
        inj_any = False
        safe_lines: List[Dict[str, Any]] = []
        for ln in (ev.get("log_lines") or [])[:10]:
            txt, inj = sanitize_retrieved_text(ln.get("text") or "")
            inj_any = inj_any or inj
            safe_lines.append({"line_no": ln.get("line_no"), "text": txt, "tags": ln.get("tags", [])})
        if not safe_lines and host_events:
            tail = str(host_events[-1].get("dmesg_tail") or "")
            for idx, line in enumerate(tail.splitlines()[:10], start=1):
                txt, inj = sanitize_retrieved_text(line)
                inj_any = inj_any or inj
                if txt:
                    safe_lines.append({"line_no": idx, "text": txt, "tags": []})
        if not safe_lines:
            msg = f"No kernel log lines are currently available for {host}."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=host, evidence_meta={"entities": [host], "missing": True},
                data={"host": host, "log_lines": []}, conv_state=conv_state,
            )
        spoken = f"Retrieved {len(safe_lines)} sanitized kernel log line(s) for {host}. Latest entry: {safe_lines[0]['text']}"
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=host, injection_flagged=inj_any,
            evidence_meta={
                "entities": [host],
                "timestamps": [(host_events[-1] if host_events else {}).get("ts")],
                "sources": ["kernel-dmesg"],
                "simulated": bool((host_events[-1] if host_events else {}).get("simulated")),
            },
            data={"host": host, "log_lines": safe_lines},
            conv_state=conv_state,
            stage="evidence",
            suggested_actions=["Can you fix this issue?", f"Show topology for {host}"],
        )

    def _op_plan_remediation(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        prop, err = self._resolve_proposal(principal, parsed.host, parsed.proposal_id)
        if err and err.startswith("UNAUTHORIZED:"):
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized",
                spoken_summary="You are not authorized to access that remediation proposal.",
                visible_summary=err.replace("UNAUTHORIZED: ", ""),
                http_status=403, conv_state=conv_state,
            )
        if not prop or not prop.get("preview"):
            msg = err or "No validated remediation proposal is currently available for that host."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True}, conv_state=conv_state,
            )
        prev = prop["preview"]
        host = prop.get("host")
        targets = prev.get("targets") or []
        iface = targets[0].get("iface") if targets else None
        params = prev.get("params") or {}
        desired_mtu = params.get("desired_mtu")
        before_mtu = (((prop.get("before_event") or {}).get("ifaces") or {}).get(iface or "") or {}).get("mtu") if iface else None
        change_desc = (
            f"update MTU on {host}/{iface} from {before_mtu or 'observed'} to {desired_mtu}"
            if desired_mtu and iface else f"run {prev.get('action')} on {host}"
        )
        spoken = (
            f"I found validated remediation proposal {prop['id']} (status: {prop['status'].replace('_', ' ')}). "
            f"Proposed action: {change_desc} in {prev.get('mode')} mode. "
            f"Risk: {prev.get('risk')}. Rollback: {prev.get('rollback')}. "
            f"Post-check: {prev.get('post_check')}. Nothing has been executed yet. "
            "Say 'proceed' to request explicit authorization."
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok",
            spoken_summary=spoken, visible_summary=spoken,
            target_host=host, target_entity=prop["id"], proposal_id=prop["id"],
            evidence_meta={
                "entities": [host, prop["id"]],
                "timestamps": [prop.get("created_at")],
                "sources": ["remediation-policy-preview"],
                "simulated": bool(prev.get("simulated")),
            },
            data={
                "proposal_id": prop["id"],
                "status": prop["status"],
                "host": host,
                "interface": iface,
                "current_mtu": before_mtu,
                "desired_mtu": desired_mtu,
                "preview_digest": prop.get("preview_digest"),
                "expires_at": prop.get("expires_at"),
                "preview": prev,
            },
            conv_state=conv_state,
            navigate_to="remediation",
            stage="remediation_preview",
            topic="remediation",
            suggested_actions=["Proceed with this fix", f"Show incident evidence for {host}"],
        )

    # ------------------------------------------------------------------
    # Read-only operations (preserved & enhanced with conversation context)
    # ------------------------------------------------------------------
    def _op_server_status(self, *, principal, transcript, input_mode, parsed, page, page_size, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        auth_hosts = self._authorized_hosts(principal)
        events = [e for e in self.service.get_events(limit=200) if principal.can_access_host(e.get("host"))]
        decisions = [d for d in self.service.get_decisions(limit=200) if principal.can_access_host(d.get("host"))]

        if parsed.host:
            host = parsed.host
            host_events = [e for e in events if e.get("host") == host]
            host_decs = [d for d in decisions if d.get("host") == host]
            topo = self.service.policy.registry.host(host)
            if not host_events and topo is None:
                msg = f"No telemetry or topology record found for host '{host}'."
                return self._audit_and_return(
                    principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                    authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                    target_host=host, evidence_meta={"entities": [host], "uncertain": True, "missing": True},
                    conv_state=conv_state,
                )
            latest_ev = host_events[-1] if host_events else None
            latest_dec = host_decs[-1] if host_decs else None
            sim = bool((latest_ev or {}).get("simulated") or (topo or {}).get("simulated"))
            ts = (latest_ev or {}).get("ts")
            stale = _is_stale(ts, simulated=sim) if latest_ev else True
            diag = ((latest_dec or {}).get("evidence") or {}).get("inference", {})
            rem = (latest_dec or {}).get("remediation") or {}
            if latest_ev is None:
                spoken = f"{host} is in topology but has no telemetry samples yet."
            else:
                dom = diag.get("fault_domain", "UNKNOWN")
                rem_status = rem.get("status") or "no active remediation"
                tag = " (simulated)" if sim else (" (stale)" if stale else "")
                spoken = f"{host}{tag}: latest diagnosis is {dom}, remediation status is {rem_status}."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
                target_host=host, target_entity=(topo or {}).get("id"),
                proposal_id=(latest_dec or {}).get("remediation_id"),
                event_id=(latest_ev or {}).get("event_id"),
                evidence_meta={
                    "entities": [host],
                    "timestamps": [ts] if ts else [],
                    "sources": [(latest_ev or {}).get("source") or "ingested-event"] if latest_ev else ["topology"],
                    "simulated": sim,
                    "stale": stale,
                    "uncertain": latest_ev is None,
                },
                data={
                    "host": host,
                    "topology_resolved": topo is not None,
                    "latest_event_id": (latest_ev or {}).get("event_id"),
                    "latest_ts": ts,
                    "fault_domain": diag.get("fault_domain"),
                    "diagnosis_statement": diag.get("statement"),
                    "remediation_status": rem.get("status"),
                    "simulated": sim,
                },
                conv_state=conv_state,
            )

        summaries = []
        for h in auth_hosts:
            he = [e for e in events if e.get("host") == h]
            hd = [d for d in decisions if d.get("host") == h]
            last_ev = he[-1] if he else None
            last_dec = hd[-1] if hd else None
            summaries.append({
                "host": h,
                "latest_ts": (last_ev or {}).get("ts"),
                "simulated": bool((last_ev or {}).get("simulated")),
                "fault_domain": (((last_dec or {}).get("evidence") or {}).get("inference") or {}).get("fault_domain"),
                "remediation_status": ((last_dec or {}).get("remediation") or {}).get("status"),
            })
        page_items, pag = self._paginate(summaries, page, page_size)
        if not summaries:
            spoken = "No authorized hosts are currently registered in topology."
        else:
            spoken = f"Showing {len(page_items)} of {len(summaries)} authorized hosts. Ask for a specific host for detailed evidence."
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            evidence_meta={"entities": [s["host"] for s in page_items], "sources": ["topology", "telemetry"]},
            data={"hosts": page_items}, pagination=pag, conv_state=conv_state,
        )

    def _op_recent_incidents(self, *, principal, transcript, input_mode, parsed, page, page_size, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        decs = [
            d for d in reversed(self.service.get_decisions(limit=200))
            if principal.can_access_host(d.get("host"))
            and (parsed.host is None or d.get("host") == parsed.host)
            and (d.get("remediate") or ((d.get("evidence") or {}).get("inference") or {}).get("fault_domain") not in (None, "UNKNOWN"))
        ]
        items = []
        inj_any = False
        for d in decs:
            ev = d.get("evidence") or {}
            inf = ev.get("inference") or {}
            stmt, inj = sanitize_retrieved_text(inf.get("statement") or "")
            inj_any = inj_any or inj
            items.append({
                "event_id": d.get("event_id"),
                "host": d.get("host"),
                "ts": d.get("ts"),
                "fault_domain": inf.get("fault_domain"),
                "confidence": (ev.get("confidence") or {}).get("level"),
                "statement": stmt,
                "remediation_id": d.get("remediation_id"),
                "remediation_status": (d.get("remediation") or {}).get("status"),
                "simulated": bool(d.get("simulated")),
            })
        page_items, pag = self._paginate(items, page, page_size)
        if not items:
            spoken = "There are no recent incidents in your authorized host scope."
            top_host = parsed.host
            top_pid = None
        else:
            top = page_items[0]
            top_host = top["host"]
            top_pid = top["remediation_id"]
            tag = " simulated" if top["simulated"] else ""
            spoken = (
                f"Found {len(items)} recent incident(s). Top{tag} incident on {top['host']}: "
                f"{top['fault_domain']} ({top['remediation_status'] or 'no proposal'})."
            )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=top_host, proposal_id=top_pid, injection_flagged=inj_any,
            evidence_meta={
                "entities": sorted({i["host"] for i in page_items if i.get("host")}),
                "timestamps": [i["ts"] for i in page_items if i.get("ts")][:3],
                "sources": ["triage-decisions"],
                "simulated": any(i["simulated"] for i in page_items),
            },
            data={"incidents": page_items}, pagination=pag, conv_state=conv_state,
            navigate_to="incidents",
        )

    def _find_latest_decision(self, principal: VoicePrincipal, host: Optional[str], proposal_id: Optional[str]) -> Optional[Dict[str, Any]]:
        decs = list(reversed(self.service.get_decisions(limit=200)))
        for d in decs:
            if not principal.can_access_host(d.get("host")):
                continue
            if proposal_id and d.get("remediation_id") == proposal_id:
                return d
            if host and d.get("host") == host:
                return d
        if not host and not proposal_id:
            for d in decs:
                if principal.can_access_host(d.get("host")) and d.get("remediation_id"):
                    return d
            for d in decs:
                if principal.can_access_host(d.get("host")):
                    return d
        return None

    def _op_incident_evidence(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        dec = self._find_latest_decision(principal, parsed.host, parsed.proposal_id)
        if not dec or not dec.get("evidence"):
            msg = "No incident evidence found for the requested host in your authorized scope."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True, "uncertain": True},
                conv_state=conv_state,
            )
        ev = dec["evidence"]
        inf = ev.get("inference") or {}
        loc = ev.get("localization") or {}
        conf = ev.get("confidence") or {}
        inj_any = False
        safe_logs = []
        for ln in (ev.get("log_lines") or [])[:5]:
            txt, inj = sanitize_retrieved_text(ln.get("text") or "")
            inj_any = inj_any or inj
            safe_logs.append({"line_no": ln.get("line_no"), "text": txt, "tags": ln.get("tags")})
        safe_stmt, inj_s = sanitize_retrieved_text(inf.get("statement") or "")
        inj_any = inj_any or inj_s
        tag = "Simulated evidence: " if ev.get("simulated") else ""
        spoken = f"{tag}{safe_stmt} Evidence strength is {conf.get('level', 'low')} ({conf.get('supporting_checks', 0)} of {conf.get('total_checks', 0)} checks)."
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=dec.get("host"), target_entity=(loc.get("host") or {}).get("entity_id"),
            proposal_id=dec.get("remediation_id"), event_id=dec.get("event_id"),
            injection_flagged=inj_any,
            evidence_meta={
                "entities": [dec.get("host")],
                "timestamps": [dec.get("ts")],
                "sources": ["deterministic-evidence", dec.get("event_id")],
                "simulated": bool(ev.get("simulated")),
                "uncertain": conf.get("level") == "low",
            },
            data={
                "event_id": dec.get("event_id"),
                "host": dec.get("host"),
                "fault_domain": inf.get("fault_domain"),
                "status": inf.get("status"),
                "statement": safe_stmt,
                "confidence": conf,
                "localization": loc,
                "mtu_checks": ev.get("mtu_checks", []),
                "counters": ev.get("counters", []),
                "log_lines": safe_logs,
                "scope": ev.get("scope", {}),
            },
            conv_state=conv_state, stage="evidence",
        )

    def _op_server_topology(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        host = parsed.host
        if not host:
            msg = "Please specify which authorized host you want topology information for (for example, gpu-b)."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="clarification_needed", spoken_summary=msg, visible_summary=msg,
                conv_state=conv_state,
            )
        reg = self.service.policy.registry
        host_ent = reg.host(host)
        if not host_ent:
            msg = f"Host '{host}' is not present in the topology registry."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=host, evidence_meta={"entities": [host], "missing": True, "uncertain": True},
                conv_state=conv_state,
            )
        ifaces = reg.interfaces(host)
        iface_views = []
        paths = {}
        for itf in ifaces:
            peer = reg.peer(host, itf["name"])
            iface_views.append({
                "name": itf["name"],
                "entity_id": itf["id"],
                "driver": itf.get("driver"),
                "intended_mtu": itf.get("intended_mtu"),
                "peer": (
                    {"device": peer.get("switch") or peer.get("host"), "port": peer.get("name"),
                     "configured_mtu": peer.get("intended_mtu"), "shared": bool(peer.get("shared"))}
                    if peer else None
                ),
            })
            for p in reg.paths_for_entity(itf["id"]):
                paths[p["id"]] = p
        peer_desc = ", ".join(
            f"{i['name']} to {i['peer']['device']} {i['peer']['port']}"
            if i["peer"] else f"{i['name']} (peer unknown)"
            for i in iface_views
        ) or "no recorded interfaces"
        sim = bool(host_ent.get("simulated"))
        spoken = f"{'Simulated topology: ' if sim else ''}{host} has {peer_desc}."
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=host, target_entity=host_ent["id"],
            evidence_meta={
                "entities": [host_ent["id"]],
                "sources": [host_ent.get("source") or "topology-registry"],
                "simulated": sim,
            },
            data={"host": host_ent, "interfaces": iface_views, "paths": list(paths.values())},
            conv_state=conv_state,
        )

    def _op_change_correlation(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        dec = self._find_latest_decision(principal, parsed.host, parsed.proposal_id)
        if not dec or not dec.get("evidence"):
            msg = "No incident with change correlation data found in your authorized scope."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True}, conv_state=conv_state,
            )
        corr = (dec["evidence"].get("change_correlation") or {})
        raw_items = corr.get("items") or []
        safe_items = []
        inj_any = False
        for ch in raw_items[:10]:
            summary, inj = sanitize_retrieved_text(ch.get("summary") or "")
            inj_any = inj_any or inj
            safe_items.append({**ch, "summary": summary})
        relevant = [c for c in safe_items if c.get("relevance") == "relevant"]
        unrelated = [c for c in safe_items if c.get("relevance") == "unrelated"]
        if relevant:
            top = relevant[0]
            spoken = (
                f"On {dec.get('host')}, change {top['change_id']} ({top['attribute']} on {top['entity']}) "
                f"is correlated as relevant, while {len(unrelated)} other change(s) are unrelated. "
                "Note: this is correlation only, not proof of causation."
            )
        elif safe_items:
            spoken = f"Checked {len(safe_items)} recent change(s) for {dec.get('host')}; none were directly correlated with the fault."
        else:
            spoken = f"No recent changes were recorded for {dec.get('host')}."
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=dec.get("host"), injection_flagged=inj_any,
            evidence_meta={
                "entities": [dec.get("host")],
                "timestamps": [dec.get("ts")],
                "sources": ["change-correlation"],
                "simulated": bool(dec.get("simulated")),
            },
            data={"items": safe_items, "note": corr.get("note")}, conv_state=conv_state,
        )

    def _op_drift_findings(self, *, principal, transcript, input_mode, parsed, page, page_size, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        decs = [
            d for d in reversed(self.service.get_decisions(limit=200))
            if principal.can_access_host(d.get("host"))
            and (parsed.host is None or d.get("host") == parsed.host)
        ]
        seen = set()
        findings = []
        for d in decs:
            for mc in (d.get("evidence") or {}).get("mtu_checks") or []:
                if mc.get("status") != "mismatch":
                    continue
                key = (mc.get("host"), mc.get("iface"))
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "host": mc.get("host"),
                    "iface": mc.get("iface"),
                    "expected_mtu": mc.get("expected"),
                    "observed_mtu": mc.get("observed"),
                    "ts": d.get("ts"),
                    "event_id": d.get("event_id"),
                    "simulated": bool(d.get("simulated")),
                })
        page_items, pag = self._paginate(findings, page, page_size)
        if not findings:
            spoken = "No configuration or MTU drift findings detected in your authorized host scope."
            top_h = parsed.host
        else:
            f0 = page_items[0]
            top_h = f0["host"]
            spoken = (
                f"Detected {len(findings)} drift finding(s). {f0['host']} {f0['iface']} has observed MTU "
                f"{f0['observed_mtu']} versus expected {f0['expected_mtu']}."
            )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=top_h,
            evidence_meta={
                "entities": [f"{f['host']}/{f['iface']}" for f in page_items],
                "timestamps": [f["ts"] for f in page_items if f.get("ts")][:3],
                "sources": ["telemetry-vs-topology-intent"],
                "simulated": any(f["simulated"] for f in page_items),
            },
            data={"drift_findings": page_items}, pagination=pag, conv_state=conv_state,
        )

    def _resolve_proposal(self, principal: VoicePrincipal, host: Optional[str], proposal_id: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if proposal_id:
            p = self.service.get_remediation(proposal_id)
            if p is None:
                return None, f"Proposal {proposal_id} was not found."
            if not principal.can_access_host(p.get("host")):
                return None, f"UNAUTHORIZED: Proposal {proposal_id} targets host '{p.get('host')}', outside your scope."
            return p, None
        proposals = [p for p in self.service.list_remediations(limit=50) if principal.can_access_host(p.get("host"))]
        if host:
            proposals = [p for p in proposals if p.get("host") == host]
        if not proposals:
            return None, "No remediation proposals found in your authorized scope."
        pending = [p for p in proposals if p.get("status") == "pending_approval"]
        return (pending[0] if pending else proposals[0]), None

    def _op_remediation_status(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        prop, err = self._resolve_proposal(principal, parsed.host, parsed.proposal_id)
        if err and err.startswith("UNAUTHORIZED:"):
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary="You are not authorized to view that proposal.",
                visible_summary=err.replace("UNAUTHORIZED: ", ""), http_status=403, conv_state=conv_state,
            )
        if not prop:
            msg = err or "No remediation proposals found."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True}, conv_state=conv_state,
            )
        prev = prop.get("preview") or {}
        spoken = (
            f"Proposal {prop['id']} for {prop.get('host')} ({prev.get('action') or 'blocked'}) "
            f"is currently {prop['status'].replace('_', ' ')} in {prop.get('mode')} mode."
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=prop.get("host"), target_entity=prop["id"], proposal_id=prop["id"],
            evidence_meta={
                "entities": [prop.get("host"), prop["id"]],
                "timestamps": [prop.get("created_at")],
                "sources": ["remediation-policy-store"],
                "simulated": bool(prop.get("simulated_evidence") or prop.get("mode") == "simulate"),
            },
            data={"proposal": prop}, conv_state=conv_state, navigate_to="remediation",
        )

    def _op_verification_result(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        prop, err = self._resolve_proposal(principal, parsed.host, parsed.proposal_id)
        if err and err.startswith("UNAUTHORIZED:"):
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary="You are not authorized to view that verification result.",
                visible_summary=err.replace("UNAUTHORIZED: ", ""), http_status=403, conv_state=conv_state,
            )
        if not prop:
            msg = err or "No remediation proposal found."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True}, conv_state=conv_state,
            )
        ver = prop.get("verification")
        if not ver:
            msg = f"Proposal {prop['id']} on {prop.get('host')} has not been verified yet (status: {prop['status']})."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=prop.get("host"), target_entity=prop["id"], proposal_id=prop["id"],
                evidence_meta={"entities": [prop.get("host"), prop["id"]], "uncertain": True},
                data={"proposal_id": prop["id"], "status": prop["status"], "verification": None},
                conv_state=conv_state,
            )
        outcome = ver.get("outcome")
        spoken = f"Verification for {prop['id']} on {prop.get('host')} is {outcome}. {ver.get('summary', '')}"
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=prop.get("host"), target_entity=prop["id"], proposal_id=prop["id"],
            evidence_meta={
                "entities": [prop.get("host"), prop["id"]],
                "timestamps": [ver.get("ts")],
                "sources": ver.get("samples_used") or ["post-check-verifier"],
                "simulated": bool(ver.get("simulated_samples")),
                "uncertain": outcome != "passed",
            },
            data={"proposal_id": prop["id"], "status": prop["status"], "verification": ver},
            conv_state=conv_state,
        )

    # ------------------------------------------------------------------
    # Safe demo operations
    # ------------------------------------------------------------------
    def _op_demo_load(self, *, principal, transcript, input_mode, parsed, post_check=None, conv_state=None, **_) -> Tuple[Dict[str, Any], int]:
        if not (principal.can_access_host("gpu-a") and principal.can_access_host("gpu-b")):
            msg = "Unauthorized: loading the two-host GPU MTU demo requires access to gpu-a and gpu-b."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary=msg, visible_summary=msg,
                target_host="gpu-b", http_status=403, conv_state=conv_state,
            )
        variant = post_check or parsed.post_check_variant or "pass"
        demo, code = self.service.run_demo(variant)
        if code != 200:
            msg = demo.get("error", "Could not load demo.")
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="error", spoken_summary=msg, visible_summary=msg,
                http_status=code, conv_state=conv_state,
            )
        prop = demo.get("proposal") or {}
        spoken = (
            f"Loaded simulated two-host MTU demo ({variant} post-check variant). "
            f"Localized MTU mismatch on gpu-b ens1f0 (1500 vs 9000). "
            f"Proposal {prop.get('id')} is awaiting approval."
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host="gpu-b", target_entity=prop.get("id"), proposal_id=prop.get("id"),
            evidence_meta={
                "entities": ["gpu-a", "gpu-b", "leaf-1"],
                "timestamps": [demo.get("scenario_clock")],
                "sources": ["scenario-fixture:mtu_two_host.json"],
                "simulated": True,
            },
            data={"scenario_id": demo.get("scenario_id"), "post_check_variant": variant, "proposal": prop},
            conv_state=conv_state, navigate_to="demo", stage="triage",
            suggested_actions=["Investigate gpu-b", "Can you fix this issue?", "Show incident evidence for gpu-b"],
        )

    def _op_preview_remediation(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        prop, err = self._resolve_proposal(principal, parsed.host, parsed.proposal_id)
        if err and err.startswith("UNAUTHORIZED:"):
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary="You are not authorized to preview that proposal.",
                visible_summary=err.replace("UNAUTHORIZED: ", ""), http_status=403, conv_state=conv_state,
            )
        if not prop or not prop.get("preview"):
            msg = err or "No previewable remediation proposal is available."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="ok", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, evidence_meta={"missing": True}, conv_state=conv_state,
            )
        prev = prop["preview"]
        spoken = (
            f"Preview for {prop['id']}: {prev['action']} on {prop.get('host')} in {prev['mode']} mode "
            f"(risk: {prev['risk']}, digest: {prop.get('preview_digest')}). Nothing has been executed."
        )
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="ok", spoken_summary=spoken, visible_summary=spoken,
            target_host=prop.get("host"), target_entity=prop["id"], proposal_id=prop["id"],
            evidence_meta={
                "entities": [prop.get("host"), prop["id"]],
                "timestamps": [prop.get("created_at")],
                "sources": ["remediation-policy-preview"],
                "simulated": bool(prev.get("simulated")),
            },
            data={"proposal_id": prop["id"], "preview_digest": prop.get("preview_digest"), "preview": prev},
            conv_state=conv_state, navigate_to="remediation", stage="remediation_preview",
        )

    # ------------------------------------------------------------------
    # Two-step state-changing operations (readback + explicit confirmation)
    # ------------------------------------------------------------------
    def _create_pending_confirmation(self, record: Dict[str, Any]) -> Dict[str, Any]:
        cid = f"vconf-{secrets.token_hex(6)}"
        now = datetime.now(timezone.utc)
        entry = {
            **record,
            "confirmation_id": cid,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.confirmation_ttl_s)).isoformat(),
            "consumed": False,
        }
        with self._lock:
            self._pending[cid] = entry
        return entry

    def _op_demo_reset_request(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        if not (principal.can_access_host("gpu-a") and principal.can_access_host("gpu-b")):
            msg = "Unauthorized: resetting the two-host MTU demo requires access to gpu-a and gpu-b."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary=msg, visible_summary=msg,
                http_status=403, conv_state=conv_state,
            )
        readback = (
            f"Please confirm: reset only the simulated '{MTU_SCENARIO_ID}' demo records? "
            "Unrelated user events and proposals will not be touched. Say 'yes confirm' or click Confirm."
        )
        pending = self._create_pending_confirmation({
            "user_id": principal.user_id,
            "intent": "demo_reset",
            "target_host": "gpu-b",
            "target_entity": MTU_SCENARIO_ID,
            "requires_step_up": False,
            "readback": readback,
        })
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="confirmation_required",
            spoken_summary=readback, visible_summary=readback,
            target_host="gpu-b", target_entity=MTU_SCENARIO_ID,
            confirmation_id=pending["confirmation_id"],
            confirmation={
                "confirmation_id": pending["confirmation_id"],
                "intent": "demo_reset",
                "target": MTU_SCENARIO_ID,
                "readback": readback,
                "requires_step_up": False,
                "expires_at": pending["expires_at"],
            },
            conv_state=conv_state, stage="awaiting_confirmation",
        )

    def _op_approve_remediation_request(self, *, principal, transcript, input_mode, parsed, conv_state, **_) -> Tuple[Dict[str, Any], int]:
        prop, err = self._resolve_proposal(principal, parsed.host, parsed.proposal_id)
        if err and err.startswith("UNAUTHORIZED:"):
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="unauthorized", spoken_summary="You are not authorized for that host or proposal.",
                visible_summary=err.replace("UNAUTHORIZED: ", ""), http_status=403, conv_state=conv_state,
            )
        if not prop:
            msg = err or "No remediation proposal found to approve."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="clarification_needed", spoken_summary=msg, visible_summary=msg,
                target_host=parsed.host, conv_state=conv_state,
            )
        if prop.get("status") != "pending_approval":
            msg = f"Proposal {prop['id']} is '{prop.get('status')}' and cannot be approved."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=True, status="refused", spoken_summary=msg, visible_summary=msg,
                target_host=prop.get("host"), target_entity=prop["id"], http_status=409, conv_state=conv_state,
            )
        prev = prop.get("preview") or {}
        is_live_ansible = prev.get("mode") == "ansible" or prop.get("mode") == "ansible"
        if is_live_ansible:
            if not (voice_allow_ansible() and self.service.policy.mode == "ansible"):
                msg = (
                    "Refused: live infrastructure changes (ansible mode) are disabled over voice by default. "
                    "Requires explicit NBT_VOICE_ALLOW_ANSIBLE=true and NBT_REMEDIATION_MODE=ansible."
                )
                return self._audit_and_return(
                    principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                    authorized=False, status="refused", spoken_summary=msg, visible_summary=msg,
                    target_host=prop.get("host"), target_entity=prop["id"], http_status=403, conv_state=conv_state,
                )
        elif prev.get("mode") != "simulate" or prop.get("mode") != "simulate":
            msg = "Refused: unsupported remediation execution mode."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="refused", spoken_summary=msg, visible_summary=msg,
                target_host=prop.get("host"), target_entity=prop["id"], http_status=403, conv_state=conv_state,
            )

        if prev.get("action") == "restart_driver":
            msg = "Refused: driver restarts are disabled over voice in the MVP."
            return self._audit_and_return(
                principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
                authorized=False, status="refused", spoken_summary=msg, visible_summary=msg,
                target_host=prop.get("host"), target_entity=prop["id"], http_status=403, conv_state=conv_state,
            )

        requires_step_up = bool(
            is_live_ansible or prev.get("risk") == "high" or prev.get("shared_infrastructure_changed")
        )
        targets_str = ", ".join(
            f"{t.get('host')}/{t.get('iface')}" if t.get("iface") else str(t.get("host"))
            for t in prev.get("targets") or []
        ) or str(prop.get("host"))
        params = prev.get("params") or {}
        param_str = f" to MTU {params['desired_mtu']}" if "desired_mtu" in params else ""
        mode_label = "live Ansible" if is_live_ansible else "simulated"
        readback = (
            f"Please confirm {mode_label} remediation {prop['id']}: run {prev.get('action')}{param_str} "
            f"on {targets_str} (mode: {mode_label}, risk: {prev.get('risk')}, digest: {prop.get('preview_digest')}). "
            f"{'Step-up authorization or a second senior approver is required. ' if requires_step_up else ''}"
            "Say 'yes confirm' or click Confirm to proceed."
        )
        pending = self._create_pending_confirmation({
            "user_id": principal.user_id,
            "intent": "approve_remediation",
            "target_host": prop.get("host"),
            "target_entity": prop["id"],
            "proposal_id": prop["id"],
            "preview_digest": prop.get("preview_digest"),
            "action": prev.get("action"),
            "mode": prop.get("mode"),
            "risk": prev.get("risk"),
            "requires_step_up": requires_step_up,
            "readback": readback,
        })
        return self._audit_and_return(
            principal=principal, input_mode=input_mode, transcript=transcript, parsed=parsed,
            authorized=True, status="confirmation_required",
            spoken_summary=readback, visible_summary=readback,
            target_host=prop.get("host"), target_entity=prop["id"], proposal_id=prop["id"],
            confirmation_id=pending["confirmation_id"],
            evidence_meta={
                "entities": [prop.get("host"), prop["id"]],
                "timestamps": [prop.get("created_at")],
                "sources": ["remediation-policy-preview"],
                "simulated": not is_live_ansible,
            },
            confirmation={
                "confirmation_id": pending["confirmation_id"],
                "intent": "approve_remediation",
                "proposal_id": prop["id"],
                "preview_digest": prop.get("preview_digest"),
                "action": prev.get("action"),
                "targets": prev.get("targets"),
                "params": params,
                "mode": prev.get("mode"),
                "risk": prev.get("risk"),
                "rollback": prev.get("rollback"),
                "post_check": prev.get("post_check"),
                "command_preview": prev.get("command_preview"),
                "readback": readback,
                "requires_step_up": requires_step_up,
                "expires_at": pending["expires_at"],
            },
            conv_state=conv_state, stage="awaiting_confirmation",
        )

    # ------------------------------------------------------------------
    # Explicit confirmation handler
    # ------------------------------------------------------------------
    def handle_confirm(
        self,
        principal: VoicePrincipal,
        confirmation_id: str,
        *,
        confirm: bool,
        confirmation_phrase: Optional[str] = None,
        step_up_code: Optional[str] = None,
        second_approver_token: Optional[str] = None,
        reason: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int]:
        conv_state = self.conversations.get(principal.user_id, session_id)
        with self._lock:
            pending = self._pending.get(confirmation_id)

        if pending is None:
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "",
                parsed=None, authorized=False, status="error",
                spoken_summary="That confirmation request was not found.",
                visible_summary="Confirmation ID not found or already cleared.",
                confirmation_id=confirmation_id, http_status=404, conv_state=conv_state,
            )

        if pending["user_id"] != principal.user_id:
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "",
                parsed=None, authorized=False, status="unauthorized",
                spoken_summary="You cannot confirm another user's pending operation.",
                visible_summary="Confirmation ID belongs to a different authenticated user.",
                confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                target_entity=pending.get("target_entity"), http_status=403, conv_state=conv_state,
            )

        if pending["consumed"]:
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "",
                parsed=None, authorized=True, status="conflict",
                spoken_summary="That confirmation has already been processed.",
                visible_summary="Confirmation ID was already consumed.",
                confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                target_entity=pending.get("target_entity"), http_status=409, conv_state=conv_state,
            )

        exp = _parse_ts(pending["expires_at"])
        if exp and datetime.now(timezone.utc) > exp:
            pending["consumed"] = True
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "",
                parsed=None, authorized=True, status="expired",
                spoken_summary="That confirmation expired. Please repeat your request to get a fresh readback.",
                visible_summary="Confirmation expired before it was decided.",
                confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                target_entity=pending.get("target_entity"), http_status=409, conv_state=conv_state,
            )

        if confirmation_phrase is not None:
            phrase_ok, phrase_msg = is_explicit_confirmation(confirmation_phrase)
            if phrase_ok is None:
                return self._audit_and_return(
                    principal=principal, input_mode="confirm", transcript=confirmation_phrase,
                    parsed=ParsedIntent(intent=pending["intent"], host=pending.get("target_host")),
                    authorized=True, status="clarification_needed",
                    spoken_summary=phrase_msg, visible_summary=phrase_msg,
                    confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                    target_entity=pending.get("target_entity"), decision="ambiguous", http_status=400,
                    conv_state=conv_state,
                )
            if phrase_ok is False:
                confirm = False

        if not confirm:
            pending["consumed"] = True
            msg = f"Cancelled {pending['intent']} for {pending.get('target_entity') or pending.get('target_host')}."
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "cancel",
                parsed=ParsedIntent(intent=pending["intent"], host=pending.get("target_host")),
                authorized=True, status="cancelled",
                spoken_summary=msg, visible_summary=msg,
                confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                target_entity=pending.get("target_entity"), decision="cancelled", http_status=200,
                conv_state=conv_state, stage="idle",
            )

        second_approver_id = None
        if pending.get("requires_step_up"):
            ok_step, step_msg, second_approver_id = self.auth.verify_step_up(
                principal, step_up_code=step_up_code, second_approver_token=second_approver_token
            )
            if not ok_step:
                return self._audit_and_return(
                    principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                    parsed=ParsedIntent(intent=pending["intent"], host=pending.get("target_host")),
                    authorized=False, status="step_up_required",
                    spoken_summary=step_msg, visible_summary=step_msg,
                    confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                    target_entity=pending.get("target_entity"), decision="step_up_failed", http_status=403,
                    conv_state=conv_state,
                )

        with self._lock:
            if pending["consumed"]:
                return self._audit_and_return(
                    principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                    parsed=None, authorized=True, status="conflict",
                    spoken_summary="That confirmation was already processed.",
                    visible_summary="Confirmation already consumed concurrently.",
                    confirmation_id=confirmation_id, http_status=409, conv_state=conv_state,
                )
            pending["consumed"] = True

        if pending["intent"] == "demo_reset":
            res = self.service.reset_demo(MTU_SCENARIO_ID)
            msg = (
                f"Reset simulated demo '{MTU_SCENARIO_ID}': removed {res['removed_records']} records "
                f"and {res['removed_proposals']} proposal(s). Unrelated user data was preserved."
            )
            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                parsed=ParsedIntent(intent="demo_reset", host="gpu-b"),
                authorized=True, status="ok",
                spoken_summary=msg, visible_summary=msg,
                confirmation_id=confirmation_id, target_host="gpu-b", target_entity=MTU_SCENARIO_ID,
                decision="confirmed", data=res, conv_state=conv_state, stage="idle",
            )

        if pending["intent"] == "approve_remediation":
            # Re-verify operator host permission & live-ansible gate before execution.
            if pending.get("target_host") and not principal.can_access_host(pending.get("target_host")):
                return self._audit_and_return(
                    principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                    parsed=ParsedIntent(intent="approve_remediation", host=pending.get("target_host"), proposal_id=pending["proposal_id"]),
                    authorized=False, status="unauthorized",
                    spoken_summary="Host authorization changed; remediation refused.",
                    visible_summary="Operator is no longer authorized for target host.",
                    confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                    target_entity=pending["proposal_id"], http_status=403, conv_state=conv_state,
                )

            approver_label = principal.user_id
            reason_note = f"voice-confirmed ({confirmation_id})"
            if second_approver_id:
                reason_note += f"; second_approver={second_approver_id}"
            if reason:
                reason_note += f": {redact_secrets(reason)}"

            proposal, code = self.service.decide_remediation(
                pending["proposal_id"],
                approved=True,
                approver=approver_label,
                preview_digest=pending["preview_digest"],
                reason=reason_note[:500],
            )
            if code != 200:
                err_msg = proposal.get("error", "Remediation approval was refused by policy.")
                return self._audit_and_return(
                    principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                    parsed=ParsedIntent(intent="approve_remediation", host=pending.get("target_host"), proposal_id=pending["proposal_id"]),
                    authorized=True, status="refused",
                    spoken_summary=err_msg, visible_summary=err_msg,
                    confirmation_id=confirmation_id, target_host=pending.get("target_host"),
                    target_entity=pending["proposal_id"], decision="policy_refused",
                    data=proposal, http_status=code, conv_state=conv_state,
                )

            ver = proposal.get("verification") or {}
            outcome = ver.get("outcome")
            status_val = proposal.get("status")
            mode_prefix = "Live Ansible" if proposal.get("mode") == "ansible" else "Simulated"
            if status_val == "resolved" and outcome == "passed":
                spoken = (
                    f"{mode_prefix} remediation {proposal['id']} on {proposal.get('host')} was approved and "
                    f"post-check verification passed (VERIFIED RESOLVED). {ver.get('summary', '')}"
                )
                voice_status = "verified_resolved"
            elif outcome == "failed" or status_val == "verification_failed":
                spoken = (
                    f"{mode_prefix} remediation {proposal['id']} ran, but post-check verification FAILED "
                    f"(VERIFICATION FAILED). The incident is NOT resolved. {ver.get('summary', '')}"
                )
                voice_status = "verification_failed"
            else:
                spoken = (
                    f"{mode_prefix} remediation {proposal['id']} ran, but post-check verification is INCONCLUSIVE "
                    f"(VERIFICATION INCONCLUSIVE, status: {status_val}). Do not treat this incident as resolved. "
                    f"{ver.get('summary', '')}"
                )
                voice_status = "verification_inconclusive"

            return self._audit_and_return(
                principal=principal, input_mode="confirm", transcript=confirmation_phrase or "confirm",
                parsed=ParsedIntent(intent="approve_remediation", host=proposal.get("host"), proposal_id=proposal["id"]),
                authorized=True, status=voice_status,
                spoken_summary=spoken, visible_summary=spoken,
                confirmation_id=confirmation_id, target_host=proposal.get("host"),
                target_entity=proposal["id"], proposal_id=proposal["id"],
                decision="confirmed",
                evidence_meta={
                    "entities": [proposal.get("host"), proposal["id"]],
                    "timestamps": [ver.get("ts") or proposal.get("updated_at")],
                    "sources": ver.get("samples_used") or ["remediation-policy"],
                    "simulated": proposal.get("mode") != "ansible",
                    "uncertain": outcome != "passed",
                },
                data={"proposal": proposal},
                http_status=200, conv_state=conv_state, stage="verified",
                suggested_actions=[
                    f"What is the verification result for {proposal.get('host')}?",
                    "Is everything running smoothly?",
                ],
            )

        return self._audit_and_return(
            principal=principal, input_mode="confirm", transcript=confirmation_phrase or "",
            parsed=None, authorized=False, status="error",
            spoken_summary="Unsupported confirmation intent.",
            visible_summary="Unsupported confirmation intent.",
            confirmation_id=confirmation_id, http_status=400, conv_state=conv_state,
        )

    def get_conversation(self, principal: VoicePrincipal, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self.conversations.get(principal.user_id, session_id).full_view()

    def clear_conversation(self, principal: VoicePrincipal, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self.conversations.clear(principal.user_id, session_id)

    def list_audit(self, principal: VoicePrincipal, limit: int = 50) -> List[Dict[str, Any]]:
        uid = None if principal.is_senior_approver() else principal.user_id
        return self.audit.list_entries(user_id=uid, limit=limit)
