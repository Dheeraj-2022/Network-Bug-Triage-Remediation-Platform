#!/usr/bin/env python3
"""
Lightweight monitoring / metrics for the AI workflow.

Collects in-process counters and timing histograms so operators can observe the
multi-agent pipeline without pulling in a heavyweight metrics stack. When the
``prometheus_client`` package is present, the same counters are also exported as
Prometheus metrics; otherwise a plain in-memory snapshot is available via
:meth:`Monitor.snapshot` (surfaced by the Flask ``/api/ai/status`` endpoint).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

LOG = logging.getLogger("nbt.ai.monitoring")

try:
    from prometheus_client import Counter as _PCounter, Histogram as _PHist  # type: ignore

    _PROM = True
except Exception:  # pragma: no cover - optional dependency
    _PROM = False


class Monitor:
    """Thread-safe counters + latency tracking for the AI workflow."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._latency_sum: Dict[str, float] = defaultdict(float)
        self._latency_count: Dict[str, int] = defaultdict(int)
        self._prom_counters: Dict[str, object] = {}
        self._prom_hist: Dict[str, object] = {}

    # ------------------------------------------------------------------
    def incr(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value
        if _PROM:
            self._prom_counter(name).inc(value)

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            self._latency_sum[name] += seconds
            self._latency_count[name] += 1
        if _PROM:
            self._prom_histogram(name).observe(seconds)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start)

    # ------------------------------------------------------------------
    def _prom_counter(self, name: str):
        if name not in self._prom_counters:
            self._prom_counters[name] = _PCounter(
                f"nbt_ai_{name}_total", f"NBT AI counter: {name}"
            )
        return self._prom_counters[name]

    def _prom_histogram(self, name: str):
        if name not in self._prom_hist:
            self._prom_hist[name] = _PHist(
                f"nbt_ai_{name}_seconds", f"NBT AI latency: {name}"
            )
        return self._prom_hist[name]

    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            latencies = {
                name: round(self._latency_sum[name] / self._latency_count[name], 4)
                for name in self._latency_count
                if self._latency_count[name]
            }
            return {
                "counters": dict(self._counters),
                "avg_latency_seconds": latencies,
                "prometheus": _PROM,
            }


# Module-level singleton
_MONITOR: Optional[Monitor] = None


def get_monitor() -> Monitor:
    global _MONITOR
    if _MONITOR is None:
        _MONITOR = Monitor()
    return _MONITOR
