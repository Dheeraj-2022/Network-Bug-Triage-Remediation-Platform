#!/usr/bin/env python3
"""
Google ADK integration for the root-cause-analysis step.

Wraps RCA reasoning as a native Google ADK :class:`LlmAgent`. When ADK is
installed *and* Vertex credentials are configured, :class:`ADKReasoner` runs the
agent against Gemini; otherwise it reports itself unavailable and the caller
falls back to the heuristic reasoner. Building the agent requires no network, so
the ADK wiring is always exercised even in offline/dev environments.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

LOG = logging.getLogger("nbt.ai.adk")

_RCA_INSTRUCTION = (
    "You are a senior network reliability engineer performing root-cause "
    "analysis on RDMA/RoCE and kernel network faults. Given telemetry, the "
    "rule-engine decision, the XGBoost priority and retrieved runbook context, "
    "respond with a single JSON object containing: root_cause, fault_domain "
    "(one of MTU_MISMATCH, RDMA_ERROR, DRIVER_FAULT, LINK_FLAP, CONGESTION, "
    "KERNEL_PANIC, UNKNOWN), confidence (0-1), evidence (list) and explanation."
)


def adk_available() -> bool:
    try:
        import google.adk  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


class ADKReasoner:
    """Runs the RCA step via a Google ADK ``LlmAgent`` when possible."""

    APP_NAME = "nbt-triage"

    def __init__(self, cfg: Any):
        self.cfg = cfg
        self._agent = None
        self._runner = None
        self._error: Optional[str] = None
        self._build()

    def _build(self) -> None:
        v = getattr(self.cfg, "vertex", None)
        if v is None or not v.enabled or not v.project:
            self._error = "Vertex disabled or no project configured"
            return
        try:
            from google.adk.agents import LlmAgent  # type: ignore

            self._agent = LlmAgent(
                name="root_cause_analyst",
                model=v.model,
                description="Root-cause analysis for network/RDMA faults.",
                instruction=_RCA_INSTRUCTION,
            )
            LOG.info("ADK LlmAgent ready (model=%s)", v.model)
        except Exception as exc:
            self._error = str(exc)
            self._agent = None
            LOG.warning("ADK agent unavailable (%s); falling back", exc)

    @property
    def available(self) -> bool:
        return self._agent is not None

    def analyze(self, system: str, prompt: str) -> str:
        """Run the ADK agent synchronously and return its raw text output."""
        if self._agent is None:
            raise RuntimeError(f"ADK agent not available: {self._error}")
        from google.adk.runners import InMemoryRunner  # type: ignore
        from google.genai import types  # type: ignore

        if self._runner is None:
            self._runner = InMemoryRunner(agent=self._agent, app_name=self.APP_NAME)

        user_id = "nbt"
        session_id = "rca"
        self._runner.session_service.create_session(
            app_name=self.APP_NAME, user_id=user_id, session_id=session_id
        )
        message = types.Content(
            role="user", parts=[types.Part(text=f"{system}\n\n{prompt}")]
        )
        chunks = []
        for event in self._runner.run(
            user_id=user_id, session_id=session_id, new_message=message
        ):
            content = getattr(event, "content", None)
            for part in getattr(content, "parts", None) or []:
                text = getattr(part, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks)


_REASONER: Optional[ADKReasoner] = None


def get_adk_reasoner(cfg: Any) -> ADKReasoner:
    global _REASONER
    if _REASONER is None:
        _REASONER = ADKReasoner(cfg)
    return _REASONER
