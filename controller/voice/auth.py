"""
Backend authentication, RBAC, per-host scoping, and step-up authorization
for the voice-first operations assistant.

Security invariants:
- Voice recognition is NEVER treated as identity verification.
- Every read and write authenticates a backend token and checks role + host scope.
- Privileged secrets are never shipped in the frontend bundle.
- In production/configured mode (NBT_VOICE_USERS_JSON or NBT_VOICE_USERS_FILE),
  demo sessions are disabled and only configured tokens are accepted.
- In local demo mode, POST /api/voice/demo-session issues an ephemeral random
  in-memory session token kept only in the browser tab's sessionStorage.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

VALID_ROLES = frozenset({"viewer", "operator", "senior_approver"})

DEMO_PROFILES: Dict[str, Dict[str, Any]] = {
    "viewer-gpu": {
        "user_id": "demo-viewer-gpu",
        "display_name": "Viewer (GPU fabric)",
        "role": "viewer",
        "allowed_hosts": ["gpu-a", "gpu-b"],
        "description": "Read-only access to gpu-a and gpu-b (demo topology).",
    },
    "operator-gpu": {
        "user_id": "demo-operator-gpu",
        "display_name": "Operator (GPU fabric)",
        "role": "operator",
        "allowed_hosts": ["gpu-a", "gpu-b"],
        "description": "Read, demo load/reset, preview, and simulated remediation approval on gpu-a and gpu-b.",
    },
    "operator-lab": {
        "user_id": "demo-operator-lab",
        "display_name": "Operator (Lab nodes)",
        "role": "operator",
        "allowed_hosts": ["node1", "node2", "node3"],
        "description": "Scoped strictly to lab hosts node1–node3 (cannot access gpu-a/gpu-b).",
    },
    "senior-approver": {
        "user_id": "demo-senior-approver",
        "display_name": "Senior Approver (Step-up)",
        "role": "senior_approver",
        "allowed_hosts": ["*"],
        "description": "Full host scope + step-up / second-approver authority for high-risk actions.",
    },
}


@dataclass(frozen=True)
class VoicePrincipal:
    user_id: str
    display_name: str
    role: str
    allowed_hosts: FrozenSet[str]
    step_up_code: Optional[str] = None
    demo_session: bool = False

    def can_access_host(self, host: Optional[str]) -> bool:
        if not host:
            return False
        return "*" in self.allowed_hosts or host in self.allowed_hosts

    def can_write(self) -> bool:
        return self.role in ("operator", "senior_approver")

    def is_senior_approver(self) -> bool:
        return self.role == "senior_approver"

    def public_view(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "role": self.role,
            "allowed_hosts": sorted(self.allowed_hosts),
            "demo_session": self.demo_session,
            "can_write": self.can_write(),
            "can_step_up": self.is_senior_approver(),
        }


class VoiceAuthManager:
    """Manages backend-enforced voice principals, RBAC, host scoping, and step-up checks."""

    def __init__(self, configured_users: Optional[Dict[str, VoicePrincipal]] = None, allow_demo_sessions: Optional[bool] = None):
        self._lock = Lock()
        self._configured: Dict[str, VoicePrincipal] = dict(configured_users or {})
        self._demo_sessions: Dict[str, VoicePrincipal] = {}
        self._explicit_demo_flag = allow_demo_sessions
        if configured_users is None:
            self._load_from_env()

    def _load_from_env(self) -> None:
        raw = os.environ.get("NBT_VOICE_USERS_JSON")
        file_path = os.environ.get("NBT_VOICE_USERS_FILE")
        if not raw and file_path and os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as fh:
                raw = fh.read()
        if not raw:
            return
        data = json.loads(raw)
        entries = data if isinstance(data, list) else [
            {"token": k, **v} for k, v in data.items() if isinstance(v, dict)
        ]
        for entry in entries:
            tok = str(entry.get("token") or "").strip()
            uid = str(entry.get("user_id") or "").strip()
            role = str(entry.get("role") or "viewer").strip().lower()
            if not tok or not uid or role not in VALID_ROLES:
                continue
            hosts = frozenset(str(h) for h in (entry.get("allowed_hosts") or []))
            self._configured[tok] = VoicePrincipal(
                user_id=uid,
                display_name=str(entry.get("display_name") or uid),
                role=role,
                allowed_hosts=hosts,
                step_up_code=entry.get("step_up_code"),
                demo_session=False,
            )

    def demo_sessions_enabled(self) -> bool:
        if self._explicit_demo_flag is not None:
            return self._explicit_demo_flag
        if self._configured:
            return False
        return os.environ.get("NBT_VOICE_DEMO_PROFILES", "1") != "0"

    def register_principal(self, token: str, principal: VoicePrincipal) -> None:
        with self._lock:
            self._configured[token] = principal

    def create_demo_session(self, profile: str) -> Tuple[Optional[Dict[str, Any]], int]:
        if not self.demo_sessions_enabled():
            return {"error": "Demo voice sessions are disabled when configured voice users are active."}, 403
        spec = DEMO_PROFILES.get(profile)
        if not spec:
            return {"error": f"Unknown demo profile '{profile}'."}, 400
        token = f"vdemo-{secrets.token_urlsafe(24)}"
        step_up_code = f"{secrets.randbelow(900000) + 100000}" if spec["role"] == "senior_approver" else None
        principal = VoicePrincipal(
            user_id=spec["user_id"],
            display_name=spec["display_name"],
            role=spec["role"],
            allowed_hosts=frozenset(spec["allowed_hosts"]),
            step_up_code=step_up_code,
            demo_session=True,
        )
        with self._lock:
            self._demo_sessions[token] = principal
        payload: Dict[str, Any] = {
            "token": token,
            "principal": principal.public_view(),
            "note": "Ephemeral in-memory local demo session token. Keep in sessionStorage only.",
        }
        if step_up_code:
            payload["step_up_code"] = step_up_code
        return payload, 200

    def authenticate(self, token: Optional[str]) -> Optional[VoicePrincipal]:
        """Constant-time token lookup. Fails closed (None) on missing or invalid tokens."""
        if not token or not isinstance(token, str):
            return None
        candidate = token.strip()
        if candidate.lower().startswith("bearer "):
            candidate = candidate[7:].strip()
        if not candidate:
            return None
        with self._lock:
            pools = (self._configured, self._demo_sessions)
            for pool in pools:
                for known, principal in pool.items():
                    if hmac.compare_digest(candidate.encode("utf-8"), known.encode("utf-8")):
                        return principal
        return None

    def verify_step_up(
        self,
        principal: VoicePrincipal,
        *,
        step_up_code: Optional[str] = None,
        second_approver_token: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify stronger step-up authorization or a distinct second authorized approver.
        Returns (ok, reason, second_approver_user_id).
        """
        if second_approver_token:
            second = self.authenticate(second_approver_token)
            if second is None:
                return False, "Second approver token is invalid.", None
            if second.user_id == principal.user_id:
                return False, "Second approver must be a different authorized user.", None
            if not second.is_senior_approver():
                return False, "Second approver must hold the senior_approver role.", None
            return True, f"Verified by second approver {second.user_id}.", second.user_id

        if step_up_code and principal.is_senior_approver() and principal.step_up_code:
            if hmac.compare_digest(step_up_code.strip().encode("utf-8"), principal.step_up_code.encode("utf-8")):
                return True, f"Step-up code verified for {principal.user_id}.", None
            return False, "Invalid step-up code.", None

        return (
            False,
            "High-risk or shared-infrastructure operation requires a valid senior_approver step-up code "
            "or a distinct senior_approver second approver token. Voice recognition alone is not identity verification.",
            None,
        )

    def config_summary(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "auth_mode": "configured_tokens" if self._configured else (
                "local_demo_sessions" if self.demo_sessions_enabled() else "disabled"
            ),
            "demo_sessions_enabled": self.demo_sessions_enabled(),
            "demo_profiles": [
                {"id": k, **{pk: pv for pk, pv in v.items()}}
                for k, v in DEMO_PROFILES.items()
            ] if self.demo_sessions_enabled() else [],
            "raw_audio_retained": False,
            "speech_privacy_note": (
                "Browser Web Speech API (if enabled by the user) may send audio to the browser vendor's speech "
                "service; the backend receives only the recognized text transcript and never stores raw audio. "
                "Use the text fallback for fully local operation."
            ),
            "llm_intent_mode": "deterministic_offline",
        }
