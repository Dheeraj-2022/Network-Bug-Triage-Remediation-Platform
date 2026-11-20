"""Translate rule / ML / AI outputs into remediation candidates for the policy."""

from typing import Any, Dict, List, Optional

from controller.rules_engine import select_playbook

ML_REMEDIATION_THRESHOLD = 0.85


def build_candidates(
    rule: Dict[str, Any],
    ml: Dict[str, Any],
    log_class: Optional[str],
    ai_remediation: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Candidates are requests only; the policy decides what (if anything) is previewed."""
    out: List[Dict[str, Any]] = []
    if rule.get("action") == "remediate":
        targets = rule.get("targets") or []
        out.append({"recommender": "rules", "playbook": select_playbook(rule.get("reason"), log_class, targets),
                    "targets": targets, "reason": rule.get("reason")})
    elif float(ml.get("priority_score", 0) or 0) >= ML_REMEDIATION_THRESHOLD:
        loc = ml.get("localization")
        out.append({"recommender": "ml", "playbook": select_playbook("ML-priority", log_class),
                    "targets": [{"host": loc}] if loc else [],
                    "reason": f"ML-priority:{ml.get('priority_score')}"})
    if ai_remediation and ai_remediation.get("playbook"):
        out.append({"recommender": "ai", "playbook": ai_remediation.get("playbook"),
                    "targets": ai_remediation.get("targets") or [],
                    "extra_vars": ai_remediation.get("extra_vars")})
    return out
