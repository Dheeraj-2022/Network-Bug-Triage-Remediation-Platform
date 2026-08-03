#!/usr/bin/env python3
"""
AI subsystem configuration.

Loads configuration for the LLM / multi-agent layer from (in priority order):
  1. Environment variables (highest priority, ideal for CI/CD & secrets)
  2. ``controller/ai/ai_config.yaml`` (checked-in defaults)
  3. Hard-coded defaults in this module

The configuration is intentionally decoupled from ``agent/config.yaml`` so the
telemetry agent and the controller AI layer can evolve independently.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a core dep but stay defensive
    yaml = None  # type: ignore

LOG = logging.getLogger("nbt.ai.config")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(_THIS_DIR, "ai_config.yaml")
KNOWLEDGE_DIR = os.path.join(_THIS_DIR, "knowledge")
STORE_DIR = os.path.join(_THIS_DIR, "store")


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class VertexConfig:
    """Google Vertex AI / Gemini connection settings."""

    enabled: bool = False
    project: Optional[str] = None
    location: str = "us-central1"
    model: str = "gemini-1.5-pro"
    temperature: float = 0.2
    max_output_tokens: int = 1024
    # Path to a service-account JSON; falls back to Application Default Creds.
    credentials_path: Optional[str] = None


@dataclass
class RetrievalConfig:
    """Hybrid retrieval settings (vector + keyword)."""

    top_k: int = 4
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    # Backend preference order; first importable wins. Fallback is always the
    # built-in numpy cosine store.
    vector_backend: str = "auto"  # auto | chroma | faiss | numpy
    knowledge_dir: str = KNOWLEDGE_DIR
    store_dir: str = STORE_DIR


@dataclass
class MemoryConfig:
    """Persistence settings for the memory subsystem."""

    enabled: bool = True
    store_dir: str = STORE_DIR
    max_incident_history: int = 5000
    max_host_history: int = 500


@dataclass
class AIConfig:
    """Top-level AI configuration object."""

    enabled: bool = True
    # When true, remediation produced by the AI planner requires explicit human
    # approval before Ansible execution.
    require_human_approval: bool = True
    # ML priority above which the AI workflow escalates to full LLM reasoning.
    escalation_priority: float = 0.5
    vertex: VertexConfig = field(default_factory=VertexConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[str] = None) -> "AIConfig":
        cfg = cls()
        file_path = path or DEFAULT_CONFIG_PATH
        cfg._apply_file(file_path)
        cfg._apply_env()
        return cfg

    def _apply_file(self, path: str) -> None:
        if not os.path.exists(path):
            LOG.debug("AI config file not found at %s; using defaults", path)
            return
        if yaml is None:
            LOG.warning("pyyaml unavailable; skipping AI config file %s", path)
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            LOG.exception("Failed to read AI config file %s", path)
            return

        self.enabled = data.get("enabled", self.enabled)
        self.require_human_approval = data.get(
            "require_human_approval", self.require_human_approval
        )
        self.escalation_priority = float(
            data.get("escalation_priority", self.escalation_priority)
        )

        for section, target in (
            ("vertex", self.vertex),
            ("retrieval", self.retrieval),
            ("memory", self.memory),
        ):
            section_data = data.get(section) or {}
            for key, value in section_data.items():
                if hasattr(target, key):
                    setattr(target, key, value)

    def _apply_env(self) -> None:
        # Global toggles
        self.enabled = _env_bool("NBT_AI_ENABLED", self.enabled)
        self.require_human_approval = _env_bool(
            "NBT_AI_REQUIRE_APPROVAL", self.require_human_approval
        )

        # Vertex AI — the presence of a project id auto-enables Vertex unless the
        # user has explicitly disabled AI.
        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("NBT_VERTEX_PROJECT")
        if project:
            self.vertex.project = project
        location = os.getenv("NBT_VERTEX_LOCATION")
        if location:
            self.vertex.location = location
        model = os.getenv("NBT_VERTEX_MODEL")
        if model:
            self.vertex.model = model
        creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv(
            "NBT_VERTEX_CREDENTIALS"
        )
        if creds:
            self.vertex.credentials_path = creds
        self.vertex.enabled = _env_bool(
            "NBT_VERTEX_ENABLED", self.vertex.enabled or bool(project)
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------
# Module-level singleton accessor
# ----------------------------------------------------------------------
_CONFIG: Optional[AIConfig] = None


def get_ai_config(reload: bool = False) -> AIConfig:
    """Return a process-wide :class:`AIConfig` singleton."""
    global _CONFIG
    if _CONFIG is None or reload:
        _CONFIG = AIConfig.load()
    return _CONFIG
