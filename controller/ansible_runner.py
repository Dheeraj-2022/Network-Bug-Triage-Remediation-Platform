#!/usr/bin/env python3
"""
Ansible runner helper.

Tries to use ansible-runner (if installed) for safe programmatic execution.
Falls back to calling `ansible-playbook` subprocess.

Provides:
    run_playbook(playbook_path, limit=None, extra_vars=None, dry_run=False) -> bool
"""

import json
import os
import shlex
import subprocess
import sys
from typing import Dict, Optional

try:
    import ansible_runner  # type: ignore
except Exception:
    ansible_runner = None

INVENTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "infra", "inventory.ini")


def _build_extra_vars_str(extra_vars: Dict) -> str:
    if not extra_vars:
        return ""
    return json.dumps(extra_vars)


def run_playbook(playbook_path: str, limit: Optional[str] = None, extra_vars: Optional[Dict] = None, dry_run: bool = True) -> bool:
    """
    Execute an Ansible playbook.

    If ansible-runner is available, use it; otherwise call ansible-playbook (subprocess).
    The function returns True if the playbook run is considered successful (return code 0).
    """
    if dry_run:
        # In dry-run, do not execute but log what we would do
        print(f"DRY-RUN playbook: {playbook_path} limit={limit} extra_vars={extra_vars}")
        return True

    if ansible_runner:
        private_data_dir = os.path.join("/tmp", "nbt_ansible_runner")
        os.makedirs(private_data_dir, exist_ok=True)
        runner = ansible_runner.run(private_data_dir=private_data_dir,
                                    playbook=playbook_path,
                                    inventory=INVENTORY_PATH,
                                    extravars=extra_vars or {},
                                    limit=limit)
        return runner.rc == 0

    # Fallback to subprocess ansible-playbook
    cmd = ["ansible-playbook", "-i", INVENTORY_PATH, playbook_path]
    if limit:
        cmd.extend(["--limit", limit])
    if extra_vars:
        cmd.extend(["--extra-vars", _build_extra_vars_str(extra_vars)])
    try:
        proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(proc.stdout)
        if proc.returncode != 0:
            print("Ansible stderr:", proc.stderr, file=sys.stderr)
        return proc.returncode == 0
    except FileNotFoundError:
        print("ansible-playbook not found in PATH. Install Ansible or install ansible-runner.", file=sys.stderr)
        return False
