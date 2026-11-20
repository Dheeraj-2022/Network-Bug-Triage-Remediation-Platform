#!/usr/bin/env python3
"""
Deterministic, topology-aware incident evidence.

Turns one telemetry event (plus optional prior/peer samples and change records)
into an inspectable evidence bundle:

* ``observed_facts`` – telemetry values, configured intent, exact log lines and
  topology relationships, each with its source.
* ``localization``   – host / interface / peer resolution against the topology
  registry. Unresolved entities are reported as such, never guessed.
* ``inference``      – the deterministic fault-domain conclusion and the facts it
  rests on. Model-generated explanations are kept elsewhere.
* ``confidence``     – an evidence-strength level (not a probability) plus the
  checks and limitations behind it.
* ``scope``          – directly affected entities vs. broader blast radius.
* ``change_correlation`` – why each recent change looks relevant or unrelated
  (correlation only, never proof of causation).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from controller.topology import TopologyRegistry

CHANGE_WINDOW_S = 24 * 3600

_LOG_PATTERNS = [
    ("mtu", re.compile(r"\bmtu\b|frame length|length error|oversiz", re.I)),
    ("rdma", re.compile(r"\bqp\b|infiniband|rdma|retry", re.I)),
    ("driver", re.compile(r"oops|call trace|driver|firmware", re.I)),
    ("panic", re.compile(r"panic", re.I)),
    ("link", re.compile(r"link (is )?(down|up)|flap", re.I)),
]

# Attributes whose change could plausibly explain each fault domain.
_DOMAIN_ATTRIBUTES = {
    "MTU_MISMATCH": {"mtu"},
    "RDMA_ERROR": {"mtu", "pfc", "ecn", "qos"},
    "DRIVER_FAULT": {"driver", "firmware", "kernel"},
    "LINK_FLAP": {"admin_state", "speed", "cable", "optics"},
}

CORRELATION_NOTE = (
    "Correlation only: a change matching the affected entity and attribute is a lead, "
    "not proof of causation. Recency alone is not treated as evidence."
)


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def telemetry_source(ev: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "telemetry",
        "ref": ev.get("event_id"),
        "host": ev.get("host"),
        "ts": ev.get("ts"),
        "simulated": bool(ev.get("simulated")),
        "origin": ev.get("source") or "ingested-event",
    }


class _Facts:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add(self, kind: str, statement: str, source: Dict[str, Any], **extra: Any) -> str:
        fid = f"F{len(self.items) + 1}"
        self.items.append({"id": fid, "kind": kind, "statement": statement, "source": source, **extra})
        return fid


def build_evidence(
    event: Dict[str, Any],
    registry: TopologyRegistry,
    *,
    previous: Optional[Dict[str, Any]] = None,
    peer_samples: Optional[Iterable[Dict[str, Any]]] = None,
    changes: Optional[Iterable[Dict[str, Any]]] = None,
    rule: Optional[Dict[str, Any]] = None,
    log_class: Optional[str] = None,
) -> Dict[str, Any]:
    rule = rule or {}
    host = event.get("host")
    ifaces = event.get("ifaces") or {}
    rdma = event.get("rdma") or {}
    src = telemetry_source(event)
    facts = _Facts()
    limitations: List[str] = []
    simulated = bool(event.get("simulated"))
    if simulated:
        limitations.append("Evidence comes from a SIMULATED fixture, not live telemetry.")

    # ---------------- host resolution ----------------
    host_ent = registry.host(host)
    loc_host = {
        "name": host,
        "resolved": host_ent is not None,
        "entity_id": host_ent["id"] if host_ent else None,
        "topology_id": host_ent["topology_id"] if host_ent else None,
        "simulated_topology": bool(host_ent and host_ent.get("simulated")),
    }
    if host_ent is None:
        limitations.append(f"Host '{host}' is not in the topology registry; no expected values or peers are known.")

    # ---------------- candidate interfaces ----------------
    candidates: List[str] = []
    for t in rule.get("targets") or []:
        if isinstance(t, dict) and t.get("iface") and t.get("host") in (None, host):
            candidates.append(str(t["iface"]))
    for nic, st in ifaces.items():
        errs = (_int(st.get("errin")) or 0) + (_int(st.get("errout")) or 0)
        itf = registry.interface(host, nic)
        mtu = _int(st.get("mtu"))
        if errs > 0 or (itf and mtu is not None and itf.get("intended_mtu") not in (None, mtu)):
            candidates.append(nic)
    candidates = list(dict.fromkeys(candidates))

    prev_ifaces = (previous or {}).get("ifaces") or {}
    window_s = None
    if previous:
        t0, t1 = _parse_ts(previous.get("ts")), _parse_ts(event.get("ts"))
        if t0 and t1 and t1 > t0:
            window_s = int((t1 - t0).total_seconds())

    loc_ifaces: List[Dict[str, Any]] = []
    mtu_checks: List[Dict[str, Any]] = []
    counters: List[Dict[str, Any]] = []
    paths: Dict[str, Dict[str, Any]] = {}
    direct: List[Dict[str, Any]] = []

    for nic in candidates:
        st = ifaces.get(nic, {})
        itf = registry.interface(host, nic)
        observed = _int(st.get("mtu"))
        f_obs = None
        if observed is not None:
            f_obs = facts.add("telemetry", f"{host}/{nic} reports MTU {observed}", src,
                              entity=itf["id"] if itf else f"iface:{host}:{nic}", attribute="mtu", value=observed)
        entry: Dict[str, Any] = {"name": nic, "resolved": itf is not None, "entity_id": itf["id"] if itf else None,
                                 "driver": itf.get("driver") if itf else None}

        # expected vs observed MTU
        expected = _int(itf.get("intended_mtu")) if itf else None
        if itf and expected is not None:
            f_cfg = facts.add(
                "config", f"Topology intent for {host}/{nic} is MTU {expected}",
                {"type": "topology", "ref": itf["id"], "topology_id": itf["topology_id"],
                 "simulated": bool(itf.get("simulated"))},
                entity=itf["id"], attribute="intended_mtu", value=expected)
        else:
            f_cfg = None
        if expected is None or observed is None:
            status = "unavailable"
            reason = ("interface not in topology registry" if not itf else
                      "no intended MTU recorded" if expected is None else "telemetry has no MTU value")
        else:
            status = "mismatch" if expected != observed else "match"
            reason = f"observed {observed} vs expected {expected}"
        mtu_checks.append({"host": host, "iface": nic, "expected": expected, "observed": observed,
                           "status": status, "reason": reason, "facts": [f for f in (f_obs, f_cfg) if f]})

        # peer resolution
        peer = registry.peer(host, nic) if itf else None
        if peer:
            f_peer = facts.add(
                "topology",
                f"{host}/{nic} is cabled to {peer.get('switch', peer.get('host'))} {peer.get('name')}",
                {"type": "topology", "ref": peer["id"], "topology_id": peer["topology_id"],
                 "simulated": bool(peer.get("simulated"))},
                entity=peer["id"])
            entry["peer"] = {"resolved": True, "entity_id": peer["id"], "kind": peer["kind"],
                             "device": peer.get("switch") or peer.get("host"), "port": peer.get("name"),
                             "configured_mtu": peer.get("intended_mtu"), "shared": bool(peer.get("shared")),
                             "facts": [f_peer],
                             "note": "Configured value from the topology record; not observed telemetry."}
        else:
            entry["peer"] = {"resolved": False,
                             "reason": "interface not in topology registry" if not itf else "no peer recorded in topology"}
            limitations.append(f"Peer of {host}/{nic} is unknown; link-partner evidence unavailable.")

        # counters
        cur_in, cur_out = _int(st.get("errin")) or 0, _int(st.get("errout")) or 0
        prev_st = prev_ifaces.get(nic)
        if prev_st is not None and window_s:
            d_in = cur_in - (_int(prev_st.get("errin")) or 0)
            d_out = cur_out - (_int(prev_st.get("errout")) or 0)
            fid = facts.add(
                "telemetry",
                f"{host}/{nic} rx errors {prev_st.get('errin', 0)} -> {cur_in} and tx errors "
                f"{prev_st.get('errout', 0)} -> {cur_out} over {window_s}s",
                {**src, "compared_with": previous.get("event_id")},
                entity=f"iface:{host}:{nic}")
            counters.append({"entity": f"{host}/{nic}", "counter": "errin", "before": cur_in - d_in, "after": cur_in,
                             "delta": d_in, "window_s": window_s, "fact": fid})
            counters.append({"entity": f"{host}/{nic}", "counter": "errout", "before": cur_out - d_out,
                             "after": cur_out, "delta": d_out, "window_s": window_s, "fact": fid})
        elif cur_in or cur_out:
            fid = facts.add("telemetry",
                            f"{host}/{nic} cumulative rx errors={cur_in}, tx errors={cur_out} (no prior sample; rate unknown)",
                            src, entity=f"iface:{host}:{nic}")
            counters.append({"entity": f"{host}/{nic}", "counter": "errin", "before": None, "after": cur_in,
                             "delta": None, "window_s": None, "fact": fid})
            limitations.append(f"No prior sample for {host}/{nic}; cannot tell whether errors are still increasing.")

        if itf:
            for p in registry.paths_for_entity(itf["id"]):
                paths[p["id"]] = p
        direct.append({"entity_id": itf["id"] if itf else f"unresolved:{host}/{nic}", "label": f"{host}/{nic}",
                       "reason": f"MTU {status}" if status != "unavailable" else "interface with errors"})
        if peer:
            direct.append({"entity_id": peer["id"], "label": f"{entry['peer']['device']} {peer.get('name')}",
                           "reason": f"link partner of {host}/{nic}"})
        loc_ifaces.append(entry)

    # RDMA counters
    qp = _int(rdma.get("qp_errors")) or 0
    if qp or (previous and (previous.get("rdma") or {}).get("qp_errors")):
        prev_qp = _int(((previous or {}).get("rdma") or {}).get("qp_errors"))
        if prev_qp is not None and window_s:
            fid = facts.add("telemetry", f"{host} RDMA qp_errors {prev_qp} -> {qp} over {window_s}s",
                            {**src, "compared_with": previous.get("event_id")}, entity=f"host:{host}")
            counters.append({"entity": host, "counter": "qp_errors", "before": prev_qp, "after": qp,
                             "delta": qp - prev_qp, "window_s": window_s, "fact": fid})
        else:
            fid = facts.add("telemetry", f"{host} RDMA qp_errors={qp} (cumulative)", src, entity=f"host:{host}")
            counters.append({"entity": host, "counter": "qp_errors", "before": None, "after": qp,
                             "delta": None, "window_s": None, "fact": fid})

    # log lines
    log_lines: List[Dict[str, Any]] = []
    for n, line in enumerate((event.get("dmesg_tail") or "").splitlines(), start=1):
        tags = [tag for tag, rx in _LOG_PATTERNS if rx.search(line)]
        if not tags:
            continue
        fid = facts.add("log", line, {"type": "log", "ref": f"{event.get('event_id')}:dmesg_tail:{n}",
                                      "host": host, "ts": event.get("ts"), "simulated": simulated},
                        tags=tags)
        log_lines.append({"line_no": n, "text": line, "tags": tags, "fact": fid})

    # path peers
    path_views: List[Dict[str, Any]] = []
    blast: List[Dict[str, Any]] = []
    peer_samples = list(peer_samples or [])
    peer_mtu_consistent: Optional[bool] = None
    for p in paths.values():
        hops = []
        for hid in p.get("hops", []):
            ent = registry.entity(hid) or {}
            hops.append({"entity_id": hid, "kind": ent.get("kind"), "name": ent.get("name"),
                         "device": ent.get("host") or ent.get("switch")})
        path_views.append({"id": p["id"], "required_mtu": p.get("required_mtu"), "purpose": p.get("purpose"),
                           "hops": hops, "source": {"type": "topology", "ref": p["id"]}})
        direct_ids = {d["entity_id"] for d in direct}
        for h in hops:
            if h["entity_id"] in direct_ids or h["entity_id"] == (host_ent or {}).get("id"):
                continue
            if h["kind"] == "switch":
                blast.append({"entity_id": h["entity_id"], "label": h["name"],
                              "reason": f"shared infrastructure on path {p['id']}"})
            elif h["kind"] == "host":
                blast.append({"entity_id": h["entity_id"], "label": h["name"],
                              "reason": f"other endpoint of path {p['id']}; its flows to {host} are affected"})
                itf_hop = next((x for x in hops if x["kind"] == "interface" and x["device"] == h["name"]), None)
                sample = next((s for s in reversed(peer_samples) if s.get("host") == h["name"]), None)
                if itf_hop and sample:
                    pm = _int(((sample.get("ifaces") or {}).get(itf_hop["name"]) or {}).get("mtu"))
                    if pm is not None:
                        facts.add("telemetry", f"Path peer {h['name']}/{itf_hop['name']} reports MTU {pm}",
                                  telemetry_source(sample), entity=itf_hop["entity_id"], attribute="mtu", value=pm)
                        consistent = p.get("required_mtu") is None or pm == p.get("required_mtu")
                        peer_mtu_consistent = consistent if peer_mtu_consistent is None else (
                            peer_mtu_consistent and consistent)
                elif itf_hop:
                    limitations.append(f"No telemetry from path peer {h['name']}; peer MTU not observed.")
    # de-duplicate blast radius entries
    seen = set()
    blast = [b for b in blast if not (b["entity_id"] in seen or seen.add(b["entity_id"]))]

    # ---------------- inference ----------------
    mismatches = [m for m in mtu_checks if m["status"] == "mismatch"]
    rising = [c for c in counters if c["delta"] and c["delta"] > 0]
    tags = {t for ln in log_lines for t in ln["tags"]}
    reasoning: List[Dict[str, Any]] = []
    if mismatches:
        m = mismatches[0]
        domain, status = "MTU_MISMATCH", "confirmed"
        statement = (f"{m['host']}/{m['iface']} runs MTU {m['observed']} but the topology intent is "
                     f"{m['expected']}")
        if path_views:
            statement += f" on {path_views[0]['id']} (required MTU {path_views[0]['required_mtu']})"
        statement += "."
        reasoning.append({"step": "Observed MTU differs from the recorded intent for the same interface.",
                          "because": m["facts"]})
        if rising:
            reasoning.append({"step": "Error counters on the localized entity increased between samples, which is "
                                      "consistent with frames larger than the receiver MTU being dropped.",
                              "because": sorted({c["fact"] for c in rising})})
        if "mtu" in tags:
            reasoning.append({"step": "Kernel log lines mention frame length / MTU.",
                              "because": [ln["fact"] for ln in log_lines if "mtu" in ln["tags"]]})
    elif log_class == "MTU_MISMATCH" or "mtu" in tags:
        domain, status = "MTU_MISMATCH", "suspected"
        statement = "Logs mention MTU/frame length, but no observed-vs-intended MTU mismatch could be verified."
        reasoning.append({"step": "Only log text supports this; expected MTU is unknown or matches.",
                          "because": [ln["fact"] for ln in log_lines if "mtu" in ln["tags"]]})
    elif "panic" in tags:
        domain, status = "KERNEL_PANIC", "suspected"
        statement = "Kernel panic signature in logs."
        reasoning.append({"step": "Log line matches a panic signature.",
                          "because": [ln["fact"] for ln in log_lines if "panic" in ln["tags"]]})
    elif log_class == "DRIVER_FAULT" or "driver" in tags:
        domain, status = "DRIVER_FAULT", "suspected"
        statement = "Driver fault signature in logs."
        reasoning.append({"step": "Log line matches a driver/firmware fault signature.",
                          "because": [ln["fact"] for ln in log_lines if "driver" in ln["tags"]]})
    elif qp or "rdma" in tags:
        domain, status = "RDMA_ERROR", "suspected"
        statement = "RDMA QP errors without a verified underlying cause."
        reasoning.append({"step": "RDMA error counters or log lines are present.",
                          "because": [c["fact"] for c in counters if c["counter"] == "qp_errors"]
                          + [ln["fact"] for ln in log_lines if "rdma" in ln["tags"]]})
    elif "link" in tags:
        domain, status = "LINK_FLAP", "suspected"
        statement = "Link state change in logs."
        reasoning.append({"step": "Log line matches a link up/down signature.",
                          "because": [ln["fact"] for ln in log_lines if "link" in ln["tags"]]})
    else:
        domain, status = "UNKNOWN", "undetermined"
        statement = "No deterministic rule explains the observed signals."

    # ---------------- confidence ----------------
    topo_ok = host_ent is not None and any(i["resolved"] for i in loc_ifaces)
    checks = [{"name": "topology_resolved", "passed": topo_ok,
               "detail": "host and interface found in topology registry" if topo_ok else "host/interface unresolved"}]
    if domain == "MTU_MISMATCH":
        checks.append({"name": "config_vs_telemetry", "passed": bool(mismatches),
                       "detail": "observed MTU differs from intent" if mismatches else "no verified mismatch"})
    checks.append({"name": "counters_rising", "passed": bool(rising),
                   "detail": "error counters increased between samples" if rising else
                   ("no prior sample" if not previous else "no counter increase")})
    domain_tag = {"MTU_MISMATCH": "mtu", "RDMA_ERROR": "rdma", "DRIVER_FAULT": "driver",
                  "KERNEL_PANIC": "panic", "LINK_FLAP": "link"}.get(domain)
    checks.append({"name": "log_corroboration", "passed": bool(domain_tag and domain_tag in tags),
                   "detail": "matching kernel log lines" if domain_tag and domain_tag in tags else "none"})
    if peer_mtu_consistent is not None:
        checks.append({"name": "path_peer_consistent", "passed": peer_mtu_consistent,
                       "detail": "path peer MTU matches path requirement" if peer_mtu_consistent
                       else "path peer MTU also deviates"})
    passed = sum(1 for c in checks if c["passed"])
    if domain == "MTU_MISMATCH" and mismatches and topo_ok and rising:
        level = "high"
    elif (domain == "MTU_MISMATCH" and mismatches) or (domain != "UNKNOWN" and topo_ok and passed >= 2):
        level = "medium"
    else:
        level = "low"
    if not topo_ok and level != "low":
        level = "low"

    # ---------------- change correlation ----------------
    direct_ids = {d["entity_id"] for d in direct}
    path_ids = {h["entity_id"] for p in path_views for h in p["hops"]}
    onset = _parse_ts(event.get("ts"))
    observed_by_entity = {f["entity"]: f.get("value") for f in facts.items
                          if f.get("attribute") == "mtu" and "entity" in f}
    correlations: List[Dict[str, Any]] = []
    for ch in changes or []:
        cts = _parse_ts(ch.get("ts"))
        age = int((onset - cts).total_seconds()) if onset and cts else None
        factors = []
        if age is None:
            relevance, score = "unknown", 0.0
            factors.append("timestamp missing or unparseable")
        elif age < 0:
            relevance, score = "unrelated", 0.0
            factors.append("change happened after the incident onset")
        elif age > CHANGE_WINDOW_S:
            continue
        else:
            ent = ch.get("entity")
            on_direct = ent in direct_ids
            on_path = ent in path_ids
            attr_match = ch.get("attribute") in _DOMAIN_ATTRIBUTES.get(domain, set())
            value_match = ent in observed_by_entity and observed_by_entity[ent] == ch.get("new_value")
            factors.append(f"{'on' if on_direct else 'not on'} a directly affected entity")
            factors.append(f"{'on' if on_path else 'not on'} the known topology path")
            factors.append(f"attribute '{ch.get('attribute')}' "
                           f"{'can' if attr_match else 'cannot'} explain {domain}")
            if value_match:
                factors.append(f"new value {ch.get('new_value')} equals the currently observed value")
            factors.append(f"{age // 60} min before onset")
            score = round(0.4 * on_direct + 0.15 * (on_path and not on_direct) + 0.3 * attr_match
                          + 0.15 * value_match, 2)
            if on_direct and attr_match:
                relevance = "relevant"
            elif (on_direct or on_path) and attr_match:
                relevance = "possibly_related"
            else:
                relevance = "unrelated"
        correlations.append({"change_id": ch.get("change_id"), "ts": ch.get("ts"), "entity": ch.get("entity"),
                             "attribute": ch.get("attribute"), "old_value": ch.get("old_value"),
                             "new_value": ch.get("new_value"), "summary": ch.get("summary"),
                             "actor": ch.get("actor"), "age_s": age, "relevance": relevance,
                             "relevance_score": score, "factors": factors})
    order = {"relevant": 0, "possibly_related": 1, "unknown": 2, "unrelated": 3}
    correlations.sort(key=lambda c: (order[c["relevance"]], -c["relevance_score"]))

    loc_status = ("resolved" if topo_ok and all(i["resolved"] and i["peer"]["resolved"] for i in loc_ifaces)
                  else "partial" if host_ent is not None else "unresolved")
    if not candidates:
        loc_status = "host_only" if host_ent else "unresolved"
        limitations.append("No interface could be localized from rules or telemetry.")

    hint = None
    if mismatches and topo_ok:
        hint = {"action": "set_mtu",
                "targets": [{"host": m["host"], "iface": m["iface"]} for m in mismatches],
                "desired_mtu": mismatches[0]["expected"]}

    return {
        "version": 1,
        "simulated": simulated,
        "event_id": event.get("event_id"),
        "observed_facts": facts.items,
        "localization": {"status": loc_status, "host": loc_host, "interfaces": loc_ifaces, "paths": path_views},
        "mtu_checks": mtu_checks,
        "counters": counters,
        "log_lines": log_lines,
        "inference": {"method": "deterministic_rules", "fault_domain": domain, "status": status,
                      "statement": statement, "reasoning": reasoning},
        "confidence": {"level": level, "checks": checks, "supporting_checks": passed, "total_checks": len(checks),
                       "limitations": list(dict.fromkeys(limitations)),
                       "note": "Evidence-strength level derived from explicit checks; not a calibrated probability."},
        "scope": {"direct": direct, "blast_radius": blast},
        "change_correlation": {"items": correlations, "note": CORRELATION_NOTE, "window_s": CHANGE_WINDOW_S},
        "remediation_hint": hint,
    }
