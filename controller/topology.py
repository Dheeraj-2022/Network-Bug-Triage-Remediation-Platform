#!/usr/bin/env python3
"""
Topology registry: the approved inventory of hosts, interfaces, switch ports
and known paths that triage localization and the remediation policy rely on.

Topologies are loaded from JSON documents (``data/topology/*.json`` by default,
override with ``NBT_TOPOLOGY_DIR``). Every document carries a ``simulated``
flag so fixture data is never presented as discovered/live topology.

The registry only answers questions about what it was told. Unknown hosts,
interfaces or peers resolve to ``None``; callers must surface that rather than
guess.
"""

from __future__ import annotations

import glob
import json
import logging
import os
from threading import Lock
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("nbt.topology")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TOPOLOGY_DIR = os.path.join(ROOT, "data", "topology")


class TopologyRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._entities: Dict[str, Dict[str, Any]] = {}
        self._hosts: Dict[str, str] = {}  # host name -> entity id

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load_dir(self, path: str) -> List[str]:
        loaded = []
        for fp in sorted(glob.glob(os.path.join(path, "*.json"))):
            try:
                loaded.append(self.load_file(fp))
            except (OSError, ValueError) as exc:
                LOG.error("Skipping invalid topology file %s: %s", fp, exc)
        return loaded

    def load_file(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return self.register(doc, source=os.path.relpath(path, ROOT).replace("\\", "/"))

    def register(self, doc: Dict[str, Any], source: str = "inline") -> str:
        """Register (or idempotently replace) a topology document."""
        topo_id = doc.get("topology_id")
        if not topo_id or not isinstance(topo_id, str):
            raise ValueError("topology document requires a string topology_id")
        entities: Dict[str, Dict[str, Any]] = {}
        hosts: Dict[str, str] = {}
        meta = {"topology_id": topo_id, "simulated": bool(doc.get("simulated", False)), "source": source}

        for h in doc.get("hosts", []):
            hid = h["id"]
            entities[hid] = {"kind": "host", **{k: v for k, v in h.items() if k != "interfaces"}, **meta}
            hosts[h["name"]] = hid
            for itf in h.get("interfaces", []):
                entities[itf["id"]] = {"kind": "interface", "host": h["name"], "host_id": hid, **itf, **meta}
        for sw in doc.get("switches", []):
            entities[sw["id"]] = {"kind": "switch", **{k: v for k, v in sw.items() if k != "ports"}, **meta}
            for p in sw.get("ports", []):
                entities[p["id"]] = {"kind": "switch_port", "switch": sw["name"], "switch_id": sw["id"],
                                     "shared": bool(sw.get("shared", True)), **p, **meta}
        for path in doc.get("paths", []):
            missing = [h for h in path.get("hops", []) if h not in entities]
            if missing:
                raise ValueError(f"path {path.get('id')} references unknown entities {missing}")

        with self._lock:
            for name, hid in hosts.items():
                owner = self._hosts.get(name)
                if owner and self._entities.get(owner, {}).get("topology_id") != topo_id:
                    raise ValueError(f"host {name} already registered by another topology")
            self._unregister_locked(topo_id)
            self._docs[topo_id] = {**doc, "_source": source}
            self._entities.update(entities)
            self._hosts.update(hosts)
        return topo_id

    def _unregister_locked(self, topo_id: str) -> None:
        if topo_id not in self._docs:
            return
        for eid in [e for e, v in self._entities.items() if v.get("topology_id") == topo_id]:
            del self._entities[eid]
        for name in [n for n, eid in self._hosts.items() if eid not in self._entities]:
            del self._hosts[name]
        del self._docs[topo_id]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def topology_ids(self) -> List[str]:
        with self._lock:
            return sorted(self._docs)

    def entity(self, entity_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not entity_id:
            return None
        with self._lock:
            ent = self._entities.get(entity_id)
            return dict(ent) if ent else None

    def host(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        with self._lock:
            hid = self._hosts.get(name)
        return self.entity(hid)

    def interfaces(self, host: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(e) for e in self._entities.values() if e["kind"] == "interface" and e.get("host") == host]

    def interface(self, host: Optional[str], iface: Optional[str]) -> Optional[Dict[str, Any]]:
        if not host or not iface:
            return None
        return next((i for i in self.interfaces(host) if i.get("name") == iface), None)

    def peer(self, host: str, iface: str) -> Optional[Dict[str, Any]]:
        itf = self.interface(host, iface)
        return self.entity(itf.get("peer")) if itf else None

    def paths_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        ent = self.entity(entity_id)
        if not ent:
            return []
        doc = self._docs.get(ent["topology_id"], {})
        return [dict(p) for p in doc.get("paths", []) if entity_id in p.get("hops", [])]

    def is_simulated(self, entity_id: str) -> bool:
        ent = self.entity(entity_id)
        return bool(ent and ent.get("simulated"))

    def view(self, topology_id: str) -> Optional[Dict[str, Any]]:
        """Nodes/links/paths for rendering one topology."""
        with self._lock:
            doc = self._docs.get(topology_id)
            if doc is None:
                return None
            ents = [dict(e) for e in self._entities.values() if e.get("topology_id") == topology_id]
        links, seen = [], set()
        for e in ents:
            peer = e.get("peer")
            if e["kind"] in ("interface", "switch_port") and peer:
                key = tuple(sorted((e["id"], peer)))
                if key not in seen:
                    seen.add(key)
                    links.append({"a": key[0], "b": key[1], "kind": "cable"})
            if e["kind"] == "interface":
                links.append({"a": e["host_id"], "b": e["id"], "kind": "member"})
            if e["kind"] == "switch_port":
                links.append({"a": e["switch_id"], "b": e["id"], "kind": "member"})
        return {
            "topology_id": topology_id,
            "label": doc.get("label"),
            "simulated": bool(doc.get("simulated", False)),
            "source": doc.get("_source"),
            "nodes": sorted(ents, key=lambda e: e["id"]),
            "links": links,
            "paths": doc.get("paths", []),
        }


_REGISTRY: Optional[TopologyRegistry] = None


def get_registry() -> TopologyRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        reg = TopologyRegistry()
        reg.load_dir(os.environ.get("NBT_TOPOLOGY_DIR", DEFAULT_TOPOLOGY_DIR))
        _REGISTRY = reg
    return _REGISTRY
