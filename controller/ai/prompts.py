#!/usr/bin/env python3
"""
Prompt management.

Centralises every LLM prompt used by the multi-agent workflow so they can be
versioned, unit-tested and audited in one place. Prompts are simple named
templates rendered with ``str.format`` semantics via :meth:`PromptLibrary.render`.

Keeping prompts here (rather than inline in each agent) gives us:
  * a single source of truth for prompt-engineering changes,
  * deterministic rendering that is trivial to snapshot-test,
  * the ability to log the exact rendered prompt for every LLM call (audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Prompt:
    """A named, versioned prompt template."""

    name: str
    version: str
    system: str
    template: str

    def render(self, **kwargs: object) -> str:
        return self.template.format(**kwargs)


# ---------------------------------------------------------------------------
# Prompt definitions
# ---------------------------------------------------------------------------
_ROOT_CAUSE = Prompt(
    name="root_cause_analysis",
    version="1.0.0",
    system=(
        "You are a senior network reliability engineer specialising in Linux "
        "kernel, NIC driver and RDMA/RoCE fault diagnosis. You reason "
        "step-by-step, cite the telemetry evidence you used, and never invent "
        "hosts or counters that are not present in the data. Respond with STRICT "
        "JSON only."
    ),
    template=(
        "A telemetry event was flagged for triage. Perform root-cause analysis.\n\n"
        "## Telemetry event\n{event_json}\n\n"
        "## Fast classifier (XGBoost) result\n{ml_json}\n\n"
        "## Rule-engine result\n{rule_json}\n\n"
        "## Retrieved knowledge (runbooks / RDMA / kernel / past incidents)\n"
        "{context}\n\n"
        "## Host & incident memory\n{memory}\n\n"
        "Return JSON with keys: "
        '"root_cause" (string), '
        '"fault_domain" (one of: MTU_MISMATCH, RDMA_ERROR, DRIVER_FAULT, '
        'KERNEL_PANIC, LINK_FLAP, CONGESTION, UNKNOWN), '
        '"confidence" (0.0-1.0 float), '
        '"evidence" (list of short strings citing counters/logs), '
        '"explanation" (concise human-readable paragraph).'
    ),
)

_REMEDIATION_PLAN = Prompt(
    name="remediation_plan",
    version="1.0.0",
    system=(
        "You are an SRE automation planner. You translate a root-cause "
        "diagnosis into a safe, minimal, auditable remediation plan that maps to "
        "the platform's existing Ansible playbooks. Prefer the least disruptive "
        "action. Respond with STRICT JSON only."
    ),
    template=(
        "Given the root-cause analysis and the available Ansible playbooks, "
        "produce a remediation plan.\n\n"
        "## Root-cause analysis\n{rca_json}\n\n"
        "## Available playbooks\n{playbooks}\n\n"
        "## Affected targets\n{targets}\n\n"
        "Return JSON with keys: "
        '"playbook" (one of the available playbook filenames, or null if no '
        'automated remediation is safe), '
        '"strategy" (e.g. canary, all-at-once), '
        '"extra_vars" (object of playbook variables), '
        '"risk" (one of: low, medium, high), '
        '"risk_rationale" (string), '
        '"requires_human_approval" (boolean), '
        '"rollback" (string describing the rollback path).'
    ),
)

_VALIDATION = Prompt(
    name="validation",
    version="1.0.0",
    system=(
        "You are a post-remediation validation agent. You judge whether a "
        "remediation resolved the fault based on before/after telemetry. Respond "
        "with STRICT JSON only."
    ),
    template=(
        "## Remediation that was applied\n{plan_json}\n\n"
        "## Pre-remediation event\n{before_json}\n\n"
        "## Post-remediation signals\n{after_json}\n\n"
        "Return JSON with keys: "
        '"resolved" (boolean), '
        '"confidence" (0.0-1.0 float), '
        '"residual_risk" (string), '
        '"recommendation" (string).'
    ),
)


class PromptLibrary:
    """Registry of all prompts keyed by name."""

    def __init__(self) -> None:
        self._prompts: Dict[str, Prompt] = {
            p.name: p
            for p in (_ROOT_CAUSE, _REMEDIATION_PLAN, _VALIDATION)
        }

    def get(self, name: str) -> Prompt:
        try:
            return self._prompts[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(
                f"Unknown prompt '{name}'. Known prompts: "
                f"{sorted(self._prompts)}"
            ) from exc

    def render(self, name: str, **kwargs: object) -> str:
        return self.get(name).render(**kwargs)

    def system(self, name: str) -> str:
        return self.get(name).system

    def names(self) -> list[str]:
        return sorted(self._prompts)


# Module-level singleton
PROMPTS = PromptLibrary()
