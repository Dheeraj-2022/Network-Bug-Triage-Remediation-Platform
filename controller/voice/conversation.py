"""
Session-isolated conversation memory and context tracker for NetResolve AI
Voice Operations Agent.

Security & privacy invariants:
- Conversation state is strictly partitioned by authenticated ``user_id`` (and
  optional ``session_id``). Context never leaks across users or sessions.
- Stored transcripts and summaries are redacted before persistence in memory.
- Raw audio is never stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from controller.voice.security import redact_secrets

MAX_TURNS_PER_SESSION = 40


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    text: str
    ts: str = field(default_factory=_iso_now)
    intent: Optional[str] = None
    status: Optional[str] = None
    host: Optional[str] = None
    proposal_id: Optional[str] = None
    navigate_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "ts": self.ts,
            "intent": self.intent,
            "status": self.status,
            "host": self.host,
            "proposal_id": self.proposal_id,
            "navigate_to": self.navigate_to,
        }


@dataclass
class ConversationState:
    user_id: str
    session_id: str = "default"
    active_topic: Optional[str] = None
    selected_host: Optional[str] = None
    selected_incident_id: Optional[str] = None
    selected_event_id: Optional[str] = None
    selected_proposal_id: Optional[str] = None
    investigation_stage: str = "idle"
    pending_confirmation_id: Optional[str] = None
    walkthrough_step: int = 0
    current_page: Optional[str] = None
    turns: List[ConversationTurn] = field(default_factory=list)
    updated_at: str = field(default_factory=_iso_now)

    def add_turn(
        self,
        role: str,
        text: str,
        *,
        intent: Optional[str] = None,
        status: Optional[str] = None,
        host: Optional[str] = None,
        proposal_id: Optional[str] = None,
        navigate_to: Optional[str] = None,
    ) -> ConversationTurn:
        turn = ConversationTurn(
            role=role,
            text=redact_secrets(text),
            intent=intent,
            status=status,
            host=host,
            proposal_id=proposal_id,
            navigate_to=navigate_to,
        )
        self.turns.append(turn)
        if len(self.turns) > MAX_TURNS_PER_SESSION:
            self.turns = self.turns[-MAX_TURNS_PER_SESSION:]
        self.updated_at = _iso_now()
        return turn

    def public_context(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active_topic": self.active_topic,
            "selected_host": self.selected_host,
            "selected_incident_id": self.selected_incident_id,
            "selected_event_id": self.selected_event_id,
            "selected_proposal_id": self.selected_proposal_id,
            "investigation_stage": self.investigation_stage,
            "pending_confirmation_id": self.pending_confirmation_id,
            "walkthrough_step": self.walkthrough_step,
            "current_page": self.current_page,
            "turn_count": len(self.turns),
            "updated_at": self.updated_at,
        }

    def full_view(self) -> Dict[str, Any]:
        return {
            "context": self.public_context(),
            "turns": [t.to_dict() for t in self.turns],
        }


class ConversationStore:
    """Thread-safe, per-user isolated in-memory conversation store."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: Dict[str, ConversationState] = {}

    def _key(self, user_id: str, session_id: Optional[str] = None) -> str:
        sid = (session_id or "default").strip() or "default"
        return f"{user_id}::{sid}"

    def get(self, user_id: str, session_id: Optional[str] = None) -> ConversationState:
        key = self._key(user_id, session_id)
        with self._lock:
            state = self._sessions.get(key)
            if state is None:
                state = ConversationState(user_id=user_id, session_id=(session_id or "default"))
                self._sessions[key] = state
            return state

    def clear(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        key = self._key(user_id, session_id)
        with self._lock:
            existed = key in self._sessions
            self._sessions[key] = ConversationState(user_id=user_id, session_id=(session_id or "default"))
        return {"ok": True, "cleared": existed, "session_id": session_id or "default"}

    def clear_all_for_user(self, user_id: str) -> int:
        prefix = f"{user_id}::"
        with self._lock:
            keys = [k for k in self._sessions if k.startswith(prefix)]
            for k in keys:
                del self._sessions[k]
            return len(keys)
