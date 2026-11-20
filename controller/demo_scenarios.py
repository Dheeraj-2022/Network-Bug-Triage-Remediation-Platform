"""
Deterministic demo scenarios.

``mtu-two-host``: gpu-a and gpu-b exchange RoCE traffic through leaf-1; a reimage
left gpu-b ens1f0 at MTU 1500 while the fabric intent is 9000. All data comes
from ``data/demo/mtu_two_host.json`` with fixed IDs and a fixed scenario clock,
and every event is tagged ``simulated=True``.
"""

import copy
import json
import os
from typing import Any, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MTU_TWO_HOST_PATH = os.path.join(ROOT, "data", "demo", "mtu_two_host.json")
MTU_SCENARIO_ID = "demo:mtu-two-host"
POST_CHECK_VARIANTS = ("pass", "fail", "inconclusive")

_CACHE: Dict[str, Any] = {}


def _tag(ev: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    ev = dict(ev)
    ev.update({"simulated": True, "scenario_id": scenario_id, "source": "scenario-fixture:mtu_two_host.json"})
    return ev


def load_mtu_two_host(path: str = MTU_TWO_HOST_PATH) -> Dict[str, Any]:
    """Return a fresh deep copy of the scenario with every event tagged as simulated."""
    if path not in _CACHE:
        with open(path, encoding="utf-8") as fh:
            _CACHE[path] = json.load(fh)
    sc = copy.deepcopy(_CACHE[path])
    sid = sc["scenario_id"]
    sc["telemetry"] = [_tag(e, sid) for e in sc["telemetry"]]
    sc["post_checks"] = {k: [_tag(e, sid) for e in v] for k, v in sc["post_checks"].items()}
    return sc
