"""
AI subsystem for the Network Bug Triage & Remediation Platform.

This package layers a multi-agent, LLM-powered reasoning pipeline on top of the
existing deterministic stack (rules engine + XGBoost + NLP embeddings + Ansible).

Design principles
-----------------
* **Non-invasive**: nothing in this package is imported by the legacy hot path
  unless explicitly enabled. The existing pipeline keeps working untouched.
* **Graceful degradation**: every optional dependency (Google Vertex AI,
  LangChain, LangGraph, Chroma/FAISS) is imported lazily. When a dependency is
  absent the component falls back to a deterministic, offline implementation so
  the platform remains fully functional in air-gapped / dev environments.
* **Reuse**: the LLM layer consumes the XGBoost classifier and NLP embeddings
  rather than replacing them. XGBoost stays the fast classifier; Gemini performs
  root-cause reasoning, explanation, remediation planning and risk analysis.

Public entry point
------------------
    from controller.ai import get_orchestrator
    orchestrator = get_orchestrator()
    result = orchestrator.run(event, base_decision)
"""

from controller.ai.config import AIConfig, get_ai_config

__all__ = ["AIConfig", "get_ai_config", "get_orchestrator"]


def get_orchestrator(config: "AIConfig | None" = None):
    """Lazy factory for the multi-agent orchestrator.

    Imported lazily so that merely importing :mod:`controller.ai` does not pull
    in the heavier agent / retrieval machinery.
    """
    from controller.ai.orchestrator import get_orchestrator as _factory

    return _factory(config)
