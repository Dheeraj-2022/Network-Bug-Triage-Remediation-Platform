"""
Deterministic post-remediation verification.

Uses the same signals as the diagnosis (interface MTU, error counters, RDMA
qp_errors). A playbook exit code is never treated as proof of a fix: with no or
insufficient post-change telemetry the outcome is ``inconclusive``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _ts(ev: Dict[str, Any]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ev.get("ts")).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iface_errors(ev: Dict[str, Any], iface: str) -> Optional[int]:
    st = (ev.get("ifaces") or {}).get(iface)
    if st is None:
        return None
    return int(st.get("errin", 0) or 0) + int(st.get("errout", 0) or 0)


def verify(
    action: str,
    targets: List[Dict[str, Any]],
    params: Dict[str, Any],
    before_event: Optional[Dict[str, Any]],
    post_samples: List[Dict[str, Any]],
    *,
    min_window_s: int = 30,
) -> Dict[str, Any]:
    if action == "collect_forensics":
        return {"outcome": "not_applicable", "checks": [], "samples_used": [],
                "summary": "Diagnostic action; there is nothing to verify."}

    checks: List[Dict[str, Any]] = []
    used: List[str] = []
    before_qp = int(((before_event or {}).get("rdma") or {}).get("qp_errors", 0) or 0)

    for t in targets:
        host, iface = t.get("host"), t.get("iface")
        samples = sorted((s for s in post_samples if s.get("host") == host and _ts(s)), key=_ts)
        used.extend(s.get("event_id") for s in samples)
        label = f"{host}/{iface}" if iface else str(host)
        src = [s.get("event_id") for s in samples]

        if action == "set_mtu":
            want = params.get("desired_mtu")
            last = samples[-1] if samples else None
            got = ((last or {}).get("ifaces") or {}).get(iface, {}).get("mtu") if last else None
            checks.append({
                "name": "mtu_applied", "target": label, "expected": want, "observed": got,
                "status": "inconclusive" if got is None else ("pass" if int(got) == want else "fail"),
                "sources": src[-1:],
            })

        # Counters must stop increasing across at least two post-change samples.
        if iface and len(samples) >= 2:
            first, last = samples[0], samples[-1]
            window = int((_ts(last) - _ts(first)).total_seconds())
            e0, e1 = _iface_errors(first, iface), _iface_errors(last, iface)
            if e0 is None or e1 is None or window < min_window_s:
                status, delta = "inconclusive", None
            else:
                delta = e1 - e0
                status = "pass" if delta <= 0 else "fail"
            checks.append({"name": "iface_errors_stable", "target": label, "expected": "delta <= 0",
                           "observed": None if delta is None else f"delta {delta} over {window}s",
                           "status": status, "sources": [first.get("event_id"), last.get("event_id")]})
            if before_qp:
                q0 = int((first.get("rdma") or {}).get("qp_errors", 0) or 0)
                q1 = int((last.get("rdma") or {}).get("qp_errors", 0) or 0)
                checks.append({"name": "rdma_qp_errors_stable", "target": host, "expected": "delta <= 0",
                               "observed": f"delta {q1 - q0} over {window}s",
                               "status": "pass" if q1 - q0 <= 0 else "fail",
                               "sources": [first.get("event_id"), last.get("event_id")]})
        else:
            checks.append({"name": "iface_errors_stable", "target": label, "expected": "delta <= 0",
                           "observed": f"{len(samples)} post-change sample(s); need >= 2",
                           "status": "inconclusive", "sources": src})

    statuses = {c["status"] for c in checks}
    outcome = "failed" if "fail" in statuses else ("inconclusive" if "inconclusive" in statuses or not checks
                                                    else "passed")
    summary = {
        "passed": "All post-checks passed; the diagnosed signals have returned to the expected state.",
        "failed": "At least one post-check failed; the incident is NOT resolved.",
        "inconclusive": "Not enough post-change telemetry to decide; the incident is NOT marked resolved.",
    }[outcome]
    return {"outcome": outcome, "checks": checks, "samples_used": [u for u in used if u], "summary": summary}
