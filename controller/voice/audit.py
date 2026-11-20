"""
SQLite-backed audit store for the voice-first operations assistant.

Records who requested each operation, redacted transcript, interpreted intent,
authorized target, confirmation ID, decision, and result.
NEVER stores raw audio or unredacted secrets.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Iterator, List, Optional

from controller.voice.security import redact_obj, redact_secrets

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_VOICE_DB_PATH = os.path.join(ROOT, "logs", "voice_audit.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    input_mode TEXT NOT NULL,
    redacted_transcript TEXT NOT NULL,
    intent TEXT,
    target_host TEXT,
    target_entity TEXT,
    authorized INTEGER NOT NULL,
    confirmation_id TEXT,
    decision TEXT,
    outcome TEXT NOT NULL,
    injection_flagged INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_voice_audit_user ON voice_audit(user_id, seq);
"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VoiceAuditStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("NBT_VOICE_AUDIT_DB", DEFAULT_VOICE_DB_PATH)
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

    def record(
        self,
        *,
        user_id: str,
        role: str,
        input_mode: str,
        transcript: str,
        intent: Optional[str],
        target_host: Optional[str],
        target_entity: Optional[str],
        authorized: bool,
        outcome: str,
        confirmation_id: Optional[str] = None,
        decision: Optional[str] = None,
        injection_flagged: bool = False,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ts = _iso_now()
        safe_transcript = redact_secrets(transcript or "")
        safe_detail = redact_obj(detail or {})
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO voice_audit (
                    ts, user_id, role, input_mode, redacted_transcript, intent,
                    target_host, target_entity, authorized, confirmation_id,
                    decision, outcome, injection_flagged, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    user_id,
                    role,
                    input_mode,
                    safe_transcript,
                    intent,
                    target_host,
                    target_entity,
                    1 if authorized else 0,
                    confirmation_id,
                    decision,
                    outcome,
                    1 if injection_flagged else 0,
                    json.dumps(safe_detail, default=str),
                ),
            )
            seq = cur.lastrowid
        return {
            "seq": seq,
            "ts": ts,
            "user_id": user_id,
            "role": role,
            "input_mode": input_mode,
            "redacted_transcript": safe_transcript,
            "intent": intent,
            "target_host": target_host,
            "target_entity": target_entity,
            "authorized": authorized,
            "confirmation_id": confirmation_id,
            "decision": decision,
            "outcome": outcome,
            "injection_flagged": injection_flagged,
            "detail": safe_detail,
        }

    def list_entries(self, *, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        q = (
            "SELECT seq, ts, user_id, role, input_mode, redacted_transcript, intent, "
            "target_host, target_entity, authorized, confirmation_id, decision, outcome, "
            "injection_flagged, detail FROM voice_audit"
        )
        args: List[Any] = []
        if user_id:
            q += " WHERE user_id = ?"
            args.append(user_id)
        q += " ORDER BY seq DESC LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [
            {
                "seq": r[0],
                "ts": r[1],
                "user_id": r[2],
                "role": r[3],
                "input_mode": r[4],
                "redacted_transcript": r[5],
                "intent": r[6],
                "target_host": r[7],
                "target_entity": r[8],
                "authorized": bool(r[9]),
                "confirmation_id": r[10],
                "decision": r[11],
                "outcome": r[12],
                "injection_flagged": bool(r[13]),
                "detail": json.loads(r[14]),
            }
            for r in rows
        ]
