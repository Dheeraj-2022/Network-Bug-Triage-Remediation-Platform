"""
Allowlisted remediation actions and input validators.

This is the only place that maps an action to a playbook. Playbook variables
are always constructed here from validated values; free text from logs, rules
or LLMs is never forwarded to Ansible.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLAYBOOK_DIR = os.path.join(ROOT, "infra", "playbooks")

HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")
# Linux interface names: max 15 chars (IFNAMSIZ - 1), no whitespace or '/'.
IFACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}$")
APPROVER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$")
MTU_RANGE = (1280, 9216)
DRIVER_ALLOWLIST = frozenset({"mlx5_core", "mlx5_ib", "rdma_rxe", "irdma", "ice", "i40e", "bnxt_en", "virtio_net"})


@dataclass(frozen=True)
class ActionSpec:
    action: str
    playbook: str
    description: str
    changes_state: bool
    risk: str
    applicable_domains: Tuple[str, ...]
    rollback: str
    post_check: str

    @property
    def playbook_path(self) -> str:
        return os.path.join(PLAYBOOK_DIR, self.playbook)


ACTIONS = {
    "set_mtu": ActionSpec(
        action="set_mtu",
        playbook="remediate_mtu.yml",
        description="Set the interface MTU to the value recorded as intended in the topology.",
        changes_state=True,
        risk="medium",
        applicable_domains=("MTU_MISMATCH",),
        rollback=("The playbook saves the previous MTU under /var/lib/network-bug-triage/mtu_backups; "
                  "restore manually with `ip link set dev <iface> mtu <previous>`. No automatic rollback."),
        post_check="Interface MTU equals the intended value and rx/tx error counters stop increasing "
                   "across two post-change samples (RDMA qp_errors too, if they were rising).",
    ),
    "restart_driver": ActionSpec(
        action="restart_driver",
        playbook="restart_driver.yml",
        description="Unload and reload the NIC kernel module recorded for the interface.",
        changes_state=True,
        risk="high",
        applicable_domains=("DRIVER_FAULT", "LINK_FLAP"),
        rollback=("Module list is saved under /var/lib/network-bug-triage/driver_backups; a failed reload "
                  "needs console access. No automatic rollback."),
        post_check="Error counters stop increasing across two post-change samples.",
    ),
    "collect_forensics": ActionSpec(
        action="collect_forensics",
        playbook="collect_forensics.yml",
        description="Collect dmesg, journal, ip/rdma link state into /var/log/network-bug-triage/forensics.",
        changes_state=False,
        risk="low",
        applicable_domains=("MTU_MISMATCH", "RDMA_ERROR", "DRIVER_FAULT", "LINK_FLAP", "KERNEL_PANIC",
                            "CONGESTION", "UNKNOWN"),
        rollback="Read-only collection (writes files under /var/log/network-bug-triage/forensics).",
        post_check="Not applicable (diagnostic action).",
    ),
}

PLAYBOOK_TO_ACTION = {spec.playbook: name for name, spec in ACTIONS.items()}


def action_for(candidate: dict) -> Optional[ActionSpec]:
    """Resolve a candidate's ``action`` or ``playbook`` to an allowlisted spec."""
    name = candidate.get("action")
    if not name and candidate.get("playbook"):
        name = PLAYBOOK_TO_ACTION.get(str(candidate["playbook"]))
    return ACTIONS.get(name) if isinstance(name, str) else None


def valid_host(name: object) -> bool:
    return isinstance(name, str) and bool(HOST_RE.match(name))


def valid_iface(name: object) -> bool:
    return isinstance(name, str) and bool(IFACE_RE.match(name))


def valid_mtu(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and MTU_RANGE[0] <= value <= MTU_RANGE[1]


def valid_approver(name: object) -> bool:
    return isinstance(name, str) and bool(APPROVER_RE.match(name))


def inventory_hosts(path: Optional[str] = None) -> set:
    """Uncommented host names in the [agents] group of the Ansible inventory."""
    path = path or os.path.join(ROOT, "infra", "inventory.ini")
    hosts, group = set(), None
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if line.startswith("[") and line.endswith("]"):
                    group = line[1:-1]
                elif group == "agents":
                    hosts.add(line.split()[0])
    except OSError:
        pass
    return hosts
