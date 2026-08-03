#!/usr/bin/env python3
"""
Memory subsystem.

Provides durable, JSON-backed memory for the multi-agent workflow. Five memory
types are maintained, per the target architecture:

* **Conversation memory** — the per-incident reasoning trace (agent messages).
* **Incident memory** — every triaged incident + its RCA and outcome.
* **Host history** — rolling per-host record of recent faults & remediations.
* **Remediation history** — every remediation attempt and its result.
* **Failure patterns** — aggregated counts of (fault_domain, playbook, resolved)
  used to bias future planning toward what has actually worked.

Storage is append-friendly JSONL / JSON under ``controller/ai/store``. Writes are
best-effort and never raise into the hot path — memory is an enhancement, not a
dependency.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from controller.ai.config import AIConfig, get_ai_config

LOG = logging.getLogger("nbt.ai.memory")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Unified memory store for the AI workflow."""

    def __init__(self, config: Optional[AIConfig] = None):
        self.cfg = config or get_ai_config()
        self.store_dir = self.cfg.memory.store_dir
        self._lock = threading.Lock()
        os.makedirs(self.store_dir, exist_ok=True)

        self._incident_path = os.path.join(self.store_dir, "incidents.jsonl")
        self._remediation_path = os.path.join(self.store_dir, "remediations.jsonl")
        self._patterns_path = os.path.join(self.store_dir, "failure_patterns.json")

        # In-memory indexes (bounded).
        self._incidents: Deque[Dict[str, Any]] = deque(
            maxlen=self.cfg.memory.max_incident_history
        )
        self._host_history: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.cfg.memory.max_host_history)
        )
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        self._patterns: Dict[str, Dict[str, int]] = {}

        self._load()

    # ------------------------------------------------------------------
    # Loading / persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.cfg.memory.enabled:
            return
        try:
            if os.path.exists(self._incident_path):
                with open(self._incident_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        self._incidents.append(rec)
                        if rec.get("host"):
                            self._host_history[rec["host"]].append(rec)
            if os.path.exists(self._patterns_path):
                with open(self._patterns_path, "r", encoding="utf-8") as fh:
                    self._patterns = json.load(fh)
        except Exception:
            LOG.exception("Failed to load memory store; continuing empty")

    def _append_jsonl(self, path: str, record: Dict[str, Any]) -> None:
        if not self.cfg.memory.enabled:
            return
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception:
            LOG.exception("Failed to append to %s", path)

    def _save_patterns(self) -> None:
        if not self.cfg.memory.enabled:
            return
        try:
            with open(self._patterns_path, "w", encoding="utf-8") as fh:
                json.dump(self._patterns, fh, indent=2)
        except Exception:
            LOG.exception("Failed to persist failure patterns")

    # ------------------------------------------------------------------
    # Conversation memory
    # ------------------------------------------------------------------
    def start_conversation(self, incident_id: str) -> None:
        with self._lock:
            self._conversations[incident_id] = []

    def add_message(self, incident_id: str, role: str, content: str) -> None:
        with self._lock:
            self._conversations.setdefault(incident_id, []).append(
                {"role": role, "content": content, "ts": _iso_now()}
            )

    def get_conversation(self, incident_id: str) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._conversations.get(incident_id, []))

    # ------------------------------------------------------------------
    # Incident memory
    # ------------------------------------------------------------------
    def record_incident(self, incident: Dict[str, Any]) -> None:
        incident = dict(incident)
        incident.setdefault("ts", _iso_now())
        with self._lock:
            self._incidents.append(incident)
            host = incident.get("host")
            if host:
                self._host_history[host].append(incident)
            self._append_jsonl(self._incident_path, incident)
            # Update failure patterns.
            self._update_pattern(incident)

    def _update_pattern(self, incident: Dict[str, Any]) -> None:
        domain = incident.get("fault_domain", "UNKNOWN")
        playbook = incident.get("playbook") or "none"
        resolved = bool(incident.get("resolved"))
        bucket = self._patterns.setdefault(
            domain, {"total": 0, "resolved": 0}
        )
        bucket["total"] += 1
        if resolved:
            bucket["resolved"] += 1
        pb_key = f"{domain}::{playbook}"
        pb_bucket = self._patterns.setdefault(
            pb_key, {"total": 0, "resolved": 0}
        )
        pb_bucket["total"] += 1
        if resolved:
            pb_bucket["resolved"] += 1
        self._save_patterns()

    # ------------------------------------------------------------------
    # Remediation history
    # ------------------------------------------------------------------
    def record_remediation(self, record: Dict[str, Any]) -> None:
        record = dict(record)
        record.setdefault("ts", _iso_now())
        with self._lock:
            self._append_jsonl(self._remediation_path, record)

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------
    def host_history(self, host: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._host_history.get(host, deque()))[-limit:]

    def similar_incidents(
        self,
        host: Optional[str] = None,
        fault_domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            candidates = list(self._incidents)
        scored: List[tuple] = []
        for inc in candidates:
            score = 0
            if host and inc.get("host") == host:
                score += 2
            if fault_domain and inc.get("fault_domain") == fault_domain:
                score += 3
            if score:
                scored.append((score, inc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [inc for _, inc in scored[:limit]]

    def failure_patterns(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return dict(self._patterns)

    def best_playbook_for(self, fault_domain: str) -> Optional[str]:
        """Return the playbook with the highest historical resolution rate."""
        best: Optional[str] = None
        best_rate = -1.0
        with self._lock:
            for key, stats in self._patterns.items():
                if "::" not in key or not key.startswith(f"{fault_domain}::"):
                    continue
                playbook = key.split("::", 1)[1]
                if playbook == "none" or stats.get("total", 0) == 0:
                    continue
                rate = stats["resolved"] / stats["total"]
                if rate > best_rate:
                    best_rate = rate
                    best = playbook
        return best

    def summary(self, host: Optional[str] = None, fault_domain: Optional[str] = None) -> str:
        """Compact memory summary for prompt injection."""
        parts: List[str] = []
        if host:
            hist = self.host_history(host, limit=5)
            if hist:
                recent = "; ".join(
                    f"{h.get('fault_domain', '?')}->{'ok' if h.get('resolved') else 'open'}"
                    for h in hist
                )
                parts.append(f"Host {host} recent faults: {recent}")
        if fault_domain:
            pat = self.failure_patterns().get(fault_domain)
            if pat:
                parts.append(
                    f"{fault_domain} history: {pat.get('resolved', 0)}/"
                    f"{pat.get('total', 0)} resolved"
                )
            best = self.best_playbook_for(fault_domain)
            if best:
                parts.append(f"Best historical playbook for {fault_domain}: {best}")
        return " | ".join(parts) if parts else "(no prior memory for this host/domain)"

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "incidents": len(self._incidents),
                "hosts_tracked": len(self._host_history),
                "conversations": len(self._conversations),
                "fault_domains": len(
                    [k for k in self._patterns if "::" not in k]
                ),
            }


# Module-level singleton
_MEMORY: Optional[MemoryStore] = None


def get_memory(config: Optional[AIConfig] = None) -> MemoryStore:
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemoryStore(config)
    return _MEMORY
