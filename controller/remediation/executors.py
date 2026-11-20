"""
Remediation executors. Only :class:`controller.remediation.policy.RemediationPolicy`
calls these, and only after an approved, validated proposal.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from controller.ansible_runner import run_playbook
from controller.remediation.catalog import ACTIONS

LOG = logging.getLogger("nbt.remediation.executor")


class SimulatedExecutor:
    """Records what would run; changes nothing. Default for API, demo and tests."""

    mode = "simulate"

    def run(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        LOG.info("SIMULATION (no change made): %s", preview["command_preview"])
        return {"ok": True, "mode": self.mode, "simulated": True,
                "detail": "Simulation only: no command was sent to any host.",
                "phases": [{"phase": "simulate", "hosts": preview["limit"], "ok": True}]}


class AnsibleExecutor:
    """Runs the allowlisted playbook canary-first. Requires explicit opt-in mode."""

    mode = "ansible"

    def run(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        spec = ACTIONS[preview["action"]]
        hosts = list(preview["limit"])
        phases = []
        canary, rest = hosts[0], hosts[1:]
        ok = run_playbook(spec.playbook_path, limit=canary, extra_vars=preview["extra_vars"], dry_run=False)
        phases.append({"phase": "canary", "hosts": [canary], "ok": ok})
        if ok and rest:
            ok = run_playbook(spec.playbook_path, limit=",".join(rest), extra_vars=preview["extra_vars"],
                              dry_run=False)
            phases.append({"phase": "remaining", "hosts": rest, "ok": ok})
        detail = "Playbook completed." if ok else (
            "Playbook failed; no automatic retry or rollback was attempted. See preview.rollback.")
        LOG.info("Ansible run %s ok=%s phases=%s", spec.playbook, ok, json.dumps(phases))
        return {"ok": ok, "mode": self.mode, "simulated": False, "detail": detail, "phases": phases}


def executor_for(mode: str):
    if mode == "simulate":
        return SimulatedExecutor()
    if mode == "ansible":
        return AnsibleExecutor()
    raise ValueError(f"unknown remediation mode {mode!r}")
