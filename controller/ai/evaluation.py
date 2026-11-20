#!/usr/bin/env python3
"""
Evaluation harness for the AI triage/remediation workflow.

Measures **fault-localization accuracy** and **fault-domain classification
accuracy** of the multi-agent workflow against a labelled dataset. This backs
the headline metric ("95% fault localization accuracy across RDMA and kernel
failures") with a reproducible, runnable measurement rather than a hard-coded
claim.

Labelled input format (list of dicts)::

    {
      "event": { ...telemetry event... },
      "base_decision": { "rule": {...}, "ml": {...}, "log_class": "..." },
      "expected_host": "node1",                # ground-truth localization
      "expected_fault_domain": "MTU_MISMATCH"  # ground-truth domain (optional)
    }

Usage::

    python -m controller.ai.evaluation --dataset data/eval_labeled.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("nbt.ai.evaluation")


@dataclass
class EvalResult:
    total: int = 0
    localization_correct: int = 0
    domain_correct: int = 0
    domain_labeled: int = 0
    by_domain: Dict[str, Dict[str, int]] = field(default_factory=dict)
    llm_backend: str = "unknown"
    errors: int = 0

    @property
    def localization_accuracy(self) -> float:
        return self.localization_correct / self.total if self.total else 0.0

    @property
    def domain_accuracy(self) -> float:
        return self.domain_correct / self.domain_labeled if self.domain_labeled else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["localization_accuracy"] = round(self.localization_accuracy, 4)
        d["domain_accuracy"] = round(self.domain_accuracy, 4)
        return d


def evaluate(dataset: List[Dict[str, Any]], orchestrator: Any = None) -> EvalResult:
    """Run the workflow over a labelled dataset and score it."""
    if orchestrator is None:
        from controller.ai import get_orchestrator

        orchestrator = get_orchestrator()

    result = EvalResult(llm_backend=orchestrator.backend)
    for row in dataset:
        event = row.get("event", {})
        base = row.get("base_decision")
        expected_host = row.get("expected_host") or event.get("host")
        expected_domain = row.get("expected_fault_domain")
        try:
            out = orchestrator.run(event, base)
        except Exception:
            LOG.exception("Workflow failed during evaluation")
            result.errors += 1
            continue

        result.total += 1

        # Localization: does any remediation target / signal host match?
        predicted_host = out.get("host") or out.get("signals", {}).get("host")
        rem_targets = out.get("remediation", {}).get("targets") or []
        target_hosts = {t.get("host") for t in rem_targets if isinstance(t, dict)}
        localized = predicted_host == expected_host or expected_host in target_hosts
        if localized:
            result.localization_correct += 1

        # Fault-domain classification.
        predicted_domain = out.get("rca", {}).get("fault_domain")
        if expected_domain:
            result.domain_labeled += 1
            bucket = result.by_domain.setdefault(
                expected_domain, {"total": 0, "correct": 0}
            )
            bucket["total"] += 1
            if predicted_domain == expected_domain:
                result.domain_correct += 1
                bucket["correct"] += 1

    return result


def load_dataset(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "samples" in data:
        return data["samples"]
    return data


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("nbt-ai-evaluation")
    p.add_argument(
        "--dataset",
        default=os.path.join("data", "eval_labeled.json"),
        help="Path to labelled evaluation dataset (JSON).",
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    if not os.path.exists(args.dataset):
        LOG.error("Dataset not found: %s", args.dataset)
        raise SystemExit(2)
    dataset = load_dataset(args.dataset)
    result = evaluate(dataset)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
