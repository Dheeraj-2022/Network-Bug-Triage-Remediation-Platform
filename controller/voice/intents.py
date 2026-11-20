"""
Strict allowlisted intent schema and deterministic parser for the voice assistant.

Only named, typed operations in ALLOWED_INTENTS can be routed to backend services.
Unknown, ambiguous, out-of-scope, or forbidden requests fail closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

READ_ONLY_INTENTS: FrozenSet[str] = frozenset({
    "server_status",
    "recent_incidents",
    "incident_evidence",
    "server_topology",
    "change_correlation",
    "drift_findings",
    "remediation_status",
    "verification_result",
})

SAFE_DEMO_INTENTS: FrozenSet[str] = frozenset({
    "demo_load",
    "demo_reset",
    "preview_remediation",
})

STATE_CHANGING_INTENTS: FrozenSet[str] = frozenset({
    "approve_remediation",
})

CONFIRMATION_REQUIRED_INTENTS: FrozenSet[str] = frozenset({
    "approve_remediation",
    "demo_reset",
})

ALLOWED_INTENTS: FrozenSet[str] = READ_ONLY_INTENTS | SAFE_DEMO_INTENTS | STATE_CHANGING_INTENTS

# Explicit unambiguous confirmation phrases (never inferred from silence or vague words).
EXPLICIT_CONFIRM_PHRASES: FrozenSet[str] = frozenset({
    "yes",
    "yes confirm",
    "confirm",
    "confirmed",
    "yes approve",
    "approve",
    "confirm action",
    "yes proceed",
    "proceed",
})

EXPLICIT_CANCEL_PHRASES: FrozenSet[str] = frozenset({
    "no",
    "cancel",
    "abort",
    "stop",
    "never mind",
    "do not proceed",
    "reject",
})

_PROPOSAL_ID_RE = re.compile(r"\b(rem-[0-9a-f]{12})\b", re.I)
_HOST_TOKEN_RE = re.compile(r"\b(gpu-[a-z0-9-]+|node\d+|vm-\d+|leaf-\d+|spine-\d+|[a-z0-9]+-[a-z0-9-]+)\b", re.I)

# Explicitly forbidden command patterns (fail closed).
_FORBIDDEN_RULES: Tuple[Tuple[str, str, re.Pattern[str]], ...] = (
    (
        "forbidden_clear_all",
        "Voice clearing of all platform state is disabled. Use the demo reset command for the demo fixture only.",
        re.compile(r"\b(clear|wipe|erase|delete|purge)\s+(all|everything|the\s+database|all\s+state|all\s+data|platform\s+state)\b", re.I),
    ),
    (
        "forbidden_driver_restart",
        "Driver restarts and kernel module reloads are disabled over voice in the MVP.",
        re.compile(r"\b(restart|reload|unload|reset)\s+(the\s+)?(driver|nic\s+driver|kernel\s+module|mlx5|irdma|module)\b|\b(rmmod|modprobe)\b", re.I),
    ),
    (
        "forbidden_live_change",
        "Live production infrastructure changes and switch reconfigurations are disabled over voice in the MVP.",
        re.compile(r"\b(production|live\s+ansible|apply\s+to\s+prod|real\s+ansible|reconfigure\s+switch|change\s+switch|modify\s+switch|ssh\s+into)\b", re.I),
    ),
    (
        "forbidden_arbitrary_exec",
        "Arbitrary shell, SQL, code execution, or external URL requests are not permitted.",
        re.compile(r"\b(run\s+shell|bash|sh\s+-c|sudo\b|rm\s+-rf|select\s+\*\s+from|drop\s+table|python\s+-c|curl\s+|wget\s+|https?://|ansible-playbook)\b", re.I),
    ),
)

_BROAD_DUMP_RE = re.compile(
    r"\b(dump|print|show|export|read|give\s+me)\s+(all|every|the\s+entire|full)\s+(inventory|hosts|servers|raw\s+logs|dmesg|logs|telemetry)\b",
    re.I,
)


@dataclass
class ParsedIntent:
    intent: Optional[str]
    host: Optional[str] = None
    proposal_id: Optional[str] = None
    post_check_variant: Optional[str] = None
    forbidden_code: Optional[str] = None
    forbidden_reason: Optional[str] = None
    broad_request: bool = False
    ambiguous: bool = False
    clarification: Optional[str] = None
    matched_rule: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "host": self.host,
            "proposal_id": self.proposal_id,
            "post_check_variant": self.post_check_variant,
            "forbidden_code": self.forbidden_code,
            "broad_request": self.broad_request,
            "ambiguous": self.ambiguous,
            "matched_rule": self.matched_rule,
        }


def _extract_host(text: str, known_hosts: Optional[List[str]] = None) -> Optional[str]:
    lower = text.lower()
    # First check exact known host names (longest first to avoid prefix collisions).
    if known_hosts:
        for h in sorted(known_hosts, key=len, reverse=True):
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(h.lower())}(?![A-Za-z0-9_-])", lower):
                return h
    # Fallback regex for host-like tokens (e.g. vm-99, node9, gpu-c) so backend auth/topology can reject unknown hosts cleanly.
    skip = {"mtu-mismatch", "two-host", "post-check", "dry-run", "read-only", "high-risk", "step-up", "demo-mtu"}
    for m in _HOST_TOKEN_RE.finditer(lower):
        cand = m.group(1)
        if cand in skip or cand.startswith("rem-") or cand.startswith("chg-") or cand.startswith("evt-"):
            continue
        return cand
    return None


def _extract_variant(text: str) -> Optional[str]:
    lower = text.lower()
    if re.search(r"\b(inconclusive)\b", lower):
        return "inconclusive"
    if re.search(r"\b(fail|failing|failed)\b", lower):
        return "fail"
    if re.search(r"\b(pass|passing|passed)\b", lower):
        return "pass"
    return None


def is_explicit_confirmation(phrase: Optional[str]) -> Tuple[Optional[bool], str]:
    """
    Evaluate a spoken confirmation phrase.
    Returns (True, reason) for unambiguous approval, (False, reason) for cancel,
    or (None, reason) for silence/ambiguous text (fail closed).
    """
    if phrase is None or not str(phrase).strip():
        return None, "No explicit confirmation phrase was provided."
    cleaned = re.sub(r"[^a-z0-9\s]", "", str(phrase).lower()).strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None, "Confirmation phrase was empty."
    if cleaned in EXPLICIT_CONFIRM_PHRASES:
        return True, f"Explicit confirmation phrase '{cleaned}' accepted."
    if cleaned in EXPLICIT_CANCEL_PHRASES:
        return False, f"Explicit cancellation phrase '{cleaned}' received."
    return None, (
        f"Ambiguous confirmation phrase '{cleaned}'. Say 'yes confirm' to proceed or 'cancel' to abort."
    )


def parse_intent(transcript: str, known_hosts: Optional[List[str]] = None) -> ParsedIntent:
    """
    Deterministically map a transcript to one allowlisted intent or fail closed.
    """
    raw = (transcript or "").strip()
    if not raw:
        return ParsedIntent(
            intent=None,
            ambiguous=True,
            clarification="I did not hear a request. Please state a supported question or command.",
        )

    # 1. Check forbidden operations first (fail closed).
    for code, reason, rx in _FORBIDDEN_RULES:
        if rx.search(raw):
            return ParsedIntent(
                intent=None,
                forbidden_code=code,
                forbidden_reason=reason,
                matched_rule=code,
            )

    # 2. Check overly broad dump requests.
    if _BROAD_DUMP_RE.search(raw):
        return ParsedIntent(
            intent=None,
            broad_request=True,
            clarification="That request is too broad. Please specify a server name (for example, gpu-b) or ask for recent incidents.",
            matched_rule="broad_dump_refused",
        )

    lower = raw.lower()
    host = _extract_host(raw, known_hosts)
    prop_m = _PROPOSAL_ID_RE.search(raw)
    proposal_id = prop_m.group(1).lower() if prop_m else None

    # 3. Safe demo operations
    if re.search(r"\b(reset|clear)\b.{0,25}\b(demo|mtu\s+demo|fixture|scenario)\b", lower):
        return ParsedIntent(intent="demo_reset", host=host, matched_rule="demo_reset")

    if re.search(r"\b(load|run|start|replay)\b.{0,25}\b(demo|mtu\s+demo|two[- ]host|fixture|scenario)\b", lower):
        return ParsedIntent(
            intent="demo_load",
            host=host,
            post_check_variant=_extract_variant(lower) or "pass",
            matched_rule="demo_load",
        )

    # 4. State-changing: approve simulated remediation
    if re.search(r"\b(approve|execute|apply|run)\b.{0,30}\b(remediation|fix|proposal|mtu\s+fix|simulated\s+fix|rem-[0-9a-f]{12})\b", lower):
        return ParsedIntent(
            intent="approve_remediation",
            host=host,
            proposal_id=proposal_id,
            matched_rule="approve_remediation",
        )

    # 5. Preview remediation
    if re.search(r"\b(preview|dry[- ]run|show\s+fix|proposed\s+fix|what\s+is\s+the\s+fix)\b", lower):
        return ParsedIntent(
            intent="preview_remediation",
            host=host,
            proposal_id=proposal_id,
            matched_rule="preview_remediation",
        )

    # 6. Read-only intents
    if re.search(r"\b(verification|post[- ]check|postcheck|did\s+the\s+fix\s+work|verify\s+result|verified)\b", lower):
        return ParsedIntent(
            intent="verification_result",
            host=host,
            proposal_id=proposal_id,
            matched_rule="verification_result",
        )

    if re.search(r"\b(remediation\s+status|approval\s+status|pending\s+approval|proposal\s+status|remediation)\b", lower):
        return ParsedIntent(
            intent="remediation_status",
            host=host,
            proposal_id=proposal_id,
            matched_rule="remediation_status",
        )

    if re.search(r"\b(change\s+correlation|recent\s+changes?|correlated\s+change|which\s+change|what\s+changed)\b", lower):
        return ParsedIntent(
            intent="change_correlation",
            host=host,
            matched_rule="change_correlation",
        )

    if re.search(r"\b(drift|mtu\s+mismatch|expected\s+versus\s+observed|expected\s+vs\s+observed|config\s+mismatch)\b", lower):
        return ParsedIntent(
            intent="drift_findings",
            host=host,
            matched_rule="drift_findings",
        )

    if re.search(r"\b(topology|neighbors?|neighbours?|peer|switch\s+port|path|blast\s+radius|connected\s+to)\b", lower):
        return ParsedIntent(
            intent="server_topology",
            host=host,
            matched_rule="server_topology",
        )

    if re.search(r"\b(evidence|why|root\s+cause|rca|diagnosis|explain\s+incident|details\s+for)\b", lower):
        return ParsedIntent(
            intent="incident_evidence",
            host=host,
            proposal_id=proposal_id,
            matched_rule="incident_evidence",
        )

    if re.search(r"\b(recent\s+incidents?|list\s+incidents?|active\s+incidents?|open\s+incidents?|incidents?)\b", lower):
        return ParsedIntent(
            intent="recent_incidents",
            host=host,
            matched_rule="recent_incidents",
        )

    if re.search(r"\b(status|health|how\s+is|check\s+server|check\s+host|server\s+health)\b", lower):
        return ParsedIntent(
            intent="server_status",
            host=host,
            matched_rule="server_status",
        )

    # 7. Ambiguous / unsupported fallback -> fail closed
    return ParsedIntent(
        intent=None,
        host=host,
        proposal_id=proposal_id,
        ambiguous=True,
        clarification=(
            "I could not map that to an allowlisted operation. Try asking for server status, recent incidents, "
            "incident evidence, topology around a host, change correlation, drift findings, remediation status, "
            "verification result, loading the MTU demo, previewing a fix, or approving a simulated remediation."
        ),
        matched_rule="unmatched_fail_closed",
    )
