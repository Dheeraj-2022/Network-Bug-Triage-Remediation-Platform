#!/usr/bin/env python3
"""
LLM client abstraction.

Provides a single :class:`LLMClient` facade that the agents use for all
reasoning. Two backends are supported:

* **Vertex AI Gemini** (:class:`VertexGeminiBackend`) — used when the
  ``google-cloud-aiplatform`` SDK is installed *and* a project is configured.
  All LLM reasoning (root-cause analysis, explanation, remediation planning,
  risk analysis) is performed here, per the target architecture.

* **Heuristic fallback** (:class:`HeuristicBackend`) — a deterministic,
  dependency-free reasoner used when Vertex is unavailable (air-gapped / dev /
  CI). It mirrors the JSON contract of the Gemini prompts so the rest of the
  pipeline behaves identically. This is what keeps the platform 100% functional
  offline while remaining production-ready when credentials are supplied.

The XGBoost classifier is intentionally *not* replaced — it remains the fast
first-pass classifier. The LLM only performs the deeper reasoning steps.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from controller.ai.config import AIConfig, get_ai_config
from controller.ai.prompts import PROMPTS

LOG = logging.getLogger("nbt.ai.llm")


# ---------------------------------------------------------------------------
# JSON extraction helper (shared by both backends)
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort extraction of a JSON object from an LLM response."""
    if not text:
        return {}
    # Strip common markdown code fences.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Find the first balanced-looking JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        LOG.debug("Could not parse JSON from LLM output: %s", text[:200])
        return {}


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class VertexGeminiBackend:
    """Google Vertex AI Gemini backend.

    Prefers the LangChain ``ChatVertexAI`` integration (so the LLM layer runs on
    LangChain) and falls back to the raw ``vertexai`` SDK if LangChain is not
    installed. Either path targets the same Gemini model on Vertex AI.
    """

    def __init__(self, cfg: AIConfig):
        self.cfg = cfg
        self._model = None
        self._chat = None  # LangChain ChatVertexAI handle when used
        self.impl = "none"  # langchain-vertex | vertexai-sdk | none
        self._init_error: Optional[str] = None
        self._initialise()

    def _initialise(self) -> None:
        v = self.cfg.vertex
        if not v.enabled or not v.project:
            self._init_error = "Vertex disabled or no project configured"
            return
        if self._init_langchain(v):
            return
        self._init_raw_sdk(v)

    def _load_credentials(self, v: Any) -> Any:
        if not v.credentials_path:
            return None
        try:
            from google.oauth2 import service_account  # type: ignore

            return service_account.Credentials.from_service_account_file(
                v.credentials_path
            )
        except Exception:
            LOG.warning(
                "Could not load Vertex credentials from %s; relying on "
                "Application Default Credentials",
                v.credentials_path,
            )
            return None

    def _init_langchain(self, v: Any) -> bool:
        try:
            from langchain_google_vertexai import ChatVertexAI  # type: ignore

            self._chat = ChatVertexAI(
                model=v.model,
                project=v.project,
                location=v.location,
                temperature=v.temperature,
                max_output_tokens=v.max_output_tokens,
                credentials=self._load_credentials(v),
            )
            self._model = self._chat
            self.impl = "langchain-vertex"
            LOG.info(
                "Vertex backend ready via LangChain ChatVertexAI "
                "(project=%s model=%s)",
                v.project,
                v.model,
            )
            return True
        except Exception as exc:
            LOG.warning("LangChain Vertex init failed (%s); trying raw SDK", exc)
            return False

    def _init_raw_sdk(self, v: Any) -> None:
        try:
            import vertexai  # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore

            init_kwargs: Dict[str, Any] = {
                "project": v.project,
                "location": v.location,
            }
            creds = self._load_credentials(v)
            if creds is not None:
                init_kwargs["credentials"] = creds
            vertexai.init(**init_kwargs)
            self._model = GenerativeModel(v.model)
            self.impl = "vertexai-sdk"
            LOG.info(
                "Vertex AI Gemini backend ready via SDK (project=%s model=%s)",
                v.project,
                v.model,
            )
        except Exception as exc:  # SDK missing or auth failure
            self._init_error = str(exc)
            self._model = None
            LOG.warning("Vertex AI unavailable (%s); using heuristic fallback", exc)

    @property
    def available(self) -> bool:
        return self._model is not None

    def generate(self, system: str, prompt: str) -> str:
        if self._model is None:
            raise RuntimeError(f"Vertex backend not available: {self._init_error}")
        if self.impl == "langchain-vertex":
            from langchain_core.messages import (  # type: ignore
                HumanMessage,
                SystemMessage,
            )

            resp = self._chat.invoke(
                [SystemMessage(content=system), HumanMessage(content=prompt)]
            )
            content = getattr(resp, "content", "")
            if isinstance(content, list):  # some models return content parts
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return content or ""

        from vertexai.generative_models import GenerationConfig  # type: ignore

        v = self.cfg.vertex
        full_prompt = f"{system}\n\n{prompt}"
        resp = self._model.generate_content(
            full_prompt,
            generation_config=GenerationConfig(
                temperature=v.temperature,
                max_output_tokens=v.max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        return getattr(resp, "text", "") or ""


class HeuristicBackend:
    """Deterministic offline reasoner.

    Produces JSON responses that satisfy the same contract as the Gemini prompts
    by combining the rule engine output, the XGBoost result and simple keyword
    heuristics over the kernel log tail. This guarantees the multi-agent pipeline
    yields useful, explainable output even with no cloud connectivity.
    """

    available = True

    _FAULT_KEYWORDS = [
        ("MTU_MISMATCH", ("mtu",)),
        ("RDMA_ERROR", ("rdma", "qp", "roce", "mlx5")),
        ("KERNEL_PANIC", ("panic", "oops", "bug:", "call trace")),
        ("DRIVER_FAULT", ("driver", "firmware", "reset")),
        ("LINK_FLAP", ("link down", "link up", "carrier")),
        ("CONGESTION", ("drop", "discard", "backpressure", "pause")),
    ]

    def generate(self, system: str, prompt: str) -> str:
        # The heuristic backend inspects the structured payload embedded in the
        # prompt rather than doing free-form generation. The orchestrator also
        # calls the typed helpers below directly, so this path is only used for
        # completeness / API symmetry.
        return json.dumps({"note": "heuristic-backend", "raw_len": len(prompt)})

    # -- typed helpers used directly by the orchestrator --------------------
    def classify_fault(self, log_text: str, rule: Dict[str, Any]) -> str:
        text = (log_text or "").lower()
        for domain, keywords in self._FAULT_KEYWORDS:
            if any(k in text for k in keywords):
                return domain
        # Fall back to rule signals.
        reason = (rule.get("reason") or "").lower()
        if "rdma" in reason:
            return "RDMA_ERROR"
        if "iface" in reason or "errors" in reason:
            return "DRIVER_FAULT"
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------
class LLMClient:
    """Unified LLM facade with automatic backend selection."""

    def __init__(self, cfg: Optional[AIConfig] = None):
        self.cfg = cfg or get_ai_config()
        self._vertex = VertexGeminiBackend(self.cfg)
        self._heuristic = HeuristicBackend()

    @property
    def backend_name(self) -> str:
        return "vertex-gemini" if self._vertex.available else "heuristic"

    @property
    def backend_impl(self) -> str:
        """How the active backend is implemented (e.g. langchain-vertex)."""
        return self._vertex.impl if self._vertex.available else "heuristic"

    @property
    def uses_llm(self) -> bool:
        return self._vertex.available

    def generate_json(self, prompt_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Render ``prompt_name`` with ``kwargs`` and return parsed JSON.

        Falls back to :meth:`HeuristicBackend` output when Vertex is not
        available. The caller supplies typed fallbacks via ``_fallback``.
        """
        fallback = kwargs.pop("_fallback", None)
        if self._vertex.available:
            try:
                system = PROMPTS.system(prompt_name)
                rendered = PROMPTS.render(prompt_name, **kwargs)
                raw = self._vertex.generate(system, rendered)
                parsed = _extract_json(raw)
                if parsed:
                    parsed["_backend"] = "vertex-gemini"
                    return parsed
                LOG.warning("Empty/invalid JSON from Vertex for %s", prompt_name)
            except Exception:
                LOG.exception("Vertex generation failed for %s", prompt_name)
        result = dict(fallback or {})
        result["_backend"] = "heuristic"
        return result

    @property
    def heuristic(self) -> HeuristicBackend:
        return self._heuristic


# Module-level singleton
_CLIENT: Optional[LLMClient] = None


def get_llm_client(cfg: Optional[AIConfig] = None) -> LLMClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = LLMClient(cfg)
    return _CLIENT
