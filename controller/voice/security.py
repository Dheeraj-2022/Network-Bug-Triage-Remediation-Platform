"""
Security utilities for the voice-first operations assistant:
- Secret/credential redaction (never exposed in responses, spoken text, or audit logs).
- Prompt-injection detection & untrusted-content neutralization.
"""

from __future__ import annotations

import os
import re
from typing import Any, List, Tuple

REDACTED = "[REDACTED]"

_SECRET_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.I)),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I)),
    ("openai_like_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("header_secret", re.compile(r"(?i)\b(x-api-key|x-voice-token|authorization)\s*[:=]\s*[^\s,;\"']+")),
    ("kv_secret", re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token|private[_-]?key|access[_-]?key|step[_-]?up[_-]?code)\s*[:=]\s*['\"]?[^\s,;\"']{3,}['\"]?")),
)

# Patterns indicative of prompt-injection or policy-bypass attempts in untrusted text.
_INJECTION_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("ignore_instructions", re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|all|system|policy|safety|security|rules?|instructions?)\b", re.I)),
    ("secret_extraction", re.compile(r"\b(reveal|show|print|dump|read|speak|tell\s+me|exfiltrate|leak)\b.{0,40}\b(api\s*key|secret|password|token|credential|private\s*key|env|environment\s*var|nbt_api_key)\b", re.I)),
    ("privilege_escalation", re.compile(r"\b(grant|give|elevate|escalate|switch|make\s+me)\b.{0,30}\b(admin|root|all\s*hosts|full\s*access|unrestricted|senior[_ ]approver|bypass)\b", re.I)),
    ("policy_bypass", re.compile(r"\b(bypass|skip|disable|turn\s+off)\b.{0,30}\b(approval|confirmation|policy|auth|authentication|rbac|check|verification)\b", re.I)),
    ("arbitrary_tool_invoke", re.compile(r"\b(execute|run|invoke|call)\b.{0,30}\b(arbitrary|shell|bash|sh\s+-c|subprocess|eval|exec|python|sql|rm\s+-rf|curl|wget)\b", re.I)),
)


def redact_secrets(text: str) -> str:
    """Redact credentials, tokens, keys, and runtime API keys from text."""
    if not text:
        return ""
    out = str(text)
    # Also redact active runtime secrets if configured in the environment.
    for env_name in ("NBT_API_KEY", "NBT_VOICE_USERS_JSON", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        val = os.environ.get(env_name)
        if val and len(val) >= 4 and env_name != "NBT_VOICE_USERS_JSON":
            out = out.replace(val, REDACTED)
    for label, rx in _SECRET_PATTERNS:
        if label in ("header_secret", "kv_secret"):
            out = rx.sub(lambda m: f"{m.group(1)}={REDACTED}", out)
        else:
            out = rx.sub(REDACTED, out)
    return out


def redact_obj(obj: Any) -> Any:
    """Recursively redact secrets from nested dicts/lists/strings."""
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, dict):
        sensitive_keys = {"token", "api_key", "password", "secret", "private_key", "step_up_code", "second_approver_token"}
        out = {}
        for k, v in obj.items():
            if str(k).lower() in sensitive_keys and v is not None:
                out[k] = REDACTED
            else:
                out[k] = redact_obj(v)
        return out
    return obj


def detect_prompt_injection(text: str) -> List[str]:
    """Return list of matched prompt-injection / policy-bypass rule names."""
    if not text:
        return []
    hits: List[str] = []
    for name, rx in _INJECTION_PATTERNS:
        if rx.search(text):
            hits.append(name)
    return hits


def sanitize_retrieved_text(text: str, max_len: int = 240) -> Tuple[str, bool]:
    """
    Sanitize untrusted telemetry, log, or change text before surfacing it.
    Returns (sanitized_text, injection_detected).
    """
    if not text:
        return "", False
    redacted = redact_secrets(text)
    hits = detect_prompt_injection(redacted)
    if hits:
        # Neutralize instruction-like retrieved text so it is never spoken or followed as a directive.
        safe = f"[untrusted telemetry text neutralized: {', '.join(hits)}]"
        return safe, True
    cleaned = " ".join(redacted.split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned, False
