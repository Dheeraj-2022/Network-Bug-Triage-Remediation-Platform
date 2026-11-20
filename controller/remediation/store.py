"""
SQLite-backed store for remediation proposals and their audit trail.

SQLite is used (stdlib, file-based) so the FastAPI service, the Kafka processor
and the approval CLI share one source of truth. Status transitions use
compare-and-set updates, so a duplicate or concurrent approval cannot execute
an action twice.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Iterator, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DB_PATH = os.path.join(ROOT, "logs", "remediation.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    target_key TEXT,
    scenario_id TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_proposals_target ON proposals(target_key, status);
CREATE TABLE IF NOT EXISTS audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    proposal_id TEXT,
    scenario_id TEXT,
    kind TEXT NOT NULL,
    actor TEXT,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_proposal ON audit(proposal_id);
"""


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProposalStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("NBT_REMEDIATION_DB", DEFAULT_DB_PATH)
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._lock = Lock()
        self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._mem_conn or sqlite3.connect(self.path, timeout=10)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                if self._mem_conn is None:
                    conn.close()

    # ------------------------------------------------------------------
    def insert(self, proposal: Dict[str, Any]) -> bool:
        """Insert; returns False if the id already exists (idempotent re-propose)."""
        with self._conn() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO proposals (id, created_at, updated_at, status, target_key, scenario_id, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (proposal["id"], proposal["created_at"], proposal["created_at"], proposal["status"],
                 proposal.get("target_key"), proposal.get("scenario_id"), json.dumps(proposal, default=str)),
            )
            return cur.rowcount == 1

    def get(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT data FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def find_open(self, target_key: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM proposals WHERE target_key = ? AND status = 'pending_approval' "
                "ORDER BY created_at DESC LIMIT 1", (target_key,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, limit: int = 50, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        q, args = "SELECT data FROM proposals", []
        if scenario_id:
            q += " WHERE scenario_id = ?"
            args.append(scenario_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        with self._conn() as c:
            return [json.loads(r[0]) for r in c.execute(q, args).fetchall()]

    def transition(self, proposal_id: str, expected_status: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Atomically apply ``updates`` iff the current status is ``expected_status``."""
        with self._conn() as c:
            row = c.execute("SELECT data, status FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
            if not row or row[1] != expected_status:
                return None
            data = json.loads(row[0])
            data.update(updates)
            data["updated_at"] = iso_now()
            cur = c.execute(
                "UPDATE proposals SET status = ?, updated_at = ?, data = ? WHERE id = ? AND status = ?",
                (data["status"], data["updated_at"], json.dumps(data, default=str), proposal_id, expected_status),
            )
            return data if cur.rowcount == 1 else None

    def delete_scenario(self, scenario_id: str) -> int:
        with self._conn() as c:
            n = c.execute("DELETE FROM proposals WHERE scenario_id = ?", (scenario_id,)).rowcount
            c.execute("DELETE FROM audit WHERE scenario_id = ?", (scenario_id,))
            return n

    # ------------------------------------------------------------------
    def audit(self, kind: str, proposal: Optional[Dict[str, Any]], detail: Dict[str, Any],
              actor: Optional[str] = None) -> Dict[str, Any]:
        entry = {"ts": iso_now(), "proposal_id": (proposal or {}).get("id"),
                 "scenario_id": (proposal or {}).get("scenario_id"), "kind": kind, "actor": actor,
                 "detail": detail}
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO audit (ts, proposal_id, scenario_id, kind, actor, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (entry["ts"], entry["proposal_id"], entry["scenario_id"], kind, actor,
                 json.dumps(detail, default=str)))
            entry["seq"] = cur.lastrowid
        return entry

    def audit_entries(self, limit: int = 100, proposal_id: Optional[str] = None,
                      scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        q, args, where = "SELECT seq, ts, proposal_id, scenario_id, kind, actor, detail FROM audit", [], []
        if proposal_id:
            where.append("proposal_id = ?")
            args.append(proposal_id)
        if scenario_id:
            where.append("scenario_id = ?")
            args.append(scenario_id)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY seq DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [{"seq": r[0], "ts": r[1], "proposal_id": r[2], "scenario_id": r[3], "kind": r[4],
                 "actor": r[5], "detail": json.loads(r[6])} for r in reversed(rows)]
