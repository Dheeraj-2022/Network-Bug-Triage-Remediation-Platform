#!/usr/bin/env python3
"""
Controller Processor (full)

- Consumes from Kafka (topic: telemetry.events) or runs in dry-run
- Runs rule-based triage (rules_engine)
- Creates log embeddings & classifies logs (nlp_parser)
- Runs ML triage (triage_model)
- Correlates recent events in-memory
- Invokes remediation via Ansible (controller.ansible_runner)
- Audit logs remediation attempts and outcomes

Usage (dry-run, no Kafka - idle until killed; use tests/validate_pipeline.py --mode dry to feed events):
    python3 controller/processor.py --dry-run

Usage (Kafka, simulate Ansible):
    python3 controller/processor.py --kafka localhost:9092 --dry-run

Usage (Kafka, REAL Ansible playbook runs against infra/inventory.ini):
    python3 controller/processor.py --kafka localhost:9092

Notes:
- --dry-run only controls Ansible execution; Kafka consumption is enabled whenever --kafka is given
- Requires controller/rules_engine.py, controller/nlp_parser.py, controller/triage_model.py
- Ansible integration uses ansible-runner if present, otherwise subprocess to ansible-playbook
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from collections import deque, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# local imports (should exist from Phase 2)
from controller.rules_engine import rule_based_triage, select_playbook
from controller.nlp_parser import LogParser
from controller.triage_model import TriageModel
from controller.ansible_runner import run_playbook

# AI multi-agent layer (optional; degrades gracefully if unavailable)
try:
    from controller.ai import get_orchestrator, get_ai_config
except Exception:  # pragma: no cover - AI layer is optional
    get_orchestrator = None
    get_ai_config = None

# kafka import guarded
try:
    from kafka import KafkaConsumer
    from kafka.errors import NoBrokersAvailable
except Exception:
    KafkaConsumer = None
    NoBrokersAvailable = Exception

LOG = logging.getLogger("nbt.processor")
LOG.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
LOG.addHandler(_handler)

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "remediation_audit.log")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "xgb_model.joblib")
PLAYBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "infra", "playbooks")
KAFKA_CONNECT_TIMEOUT_SEC = int(os.environ.get("NBT_KAFKA_CONNECT_TIMEOUT", "60"))
KAFKA_START_HINT = ("No Kafka broker reachable at %s. Start one with `docker compose up -d` "
                    "and wait for it to finish booting, or fix --kafka host:port.")


class KafkaUnavailable(RuntimeError):
    """Raised when no broker could be reached within the connect timeout."""


def iso_now():
    return datetime.now(timezone.utc).isoformat()


class SlidingStore:
    """
    In-memory sliding window of recent events for correlation.
    Not persistent - intended for quick correlation.
    """
    def __init__(self, max_events: int = 5000):
        self.events = deque(maxlen=max_events)

    def add(self, ev: Dict[str, Any]):
        self.events.append(ev)

    def recent(self, sec_window: int = 120) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc).timestamp() - sec_window
        out: List[Dict[str, Any]] = []
        for e in self.events:
            ts = e.get("ts")
            if not ts:
                continue
            try:
                if datetime.fromisoformat(ts).timestamp() >= cutoff:
                    out.append(e)
            except (ValueError, TypeError):
                # Skip events with malformed timestamps rather than crashing.
                continue
        return out

    def hosts_with_iface_errors(self, iface_name: str, min_err: int = 1) -> List[str]:
        out = []
        for e in self.recent(300):
            for nic, st in e.get("ifaces", {}).items():
                if nic == iface_name:
                    if int(st.get("errin", 0)) + int(st.get("errout", 0)) >= min_err:
                        out.append(e.get("host"))
        return out


def audit_log(entry: Dict[str, Any]):
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    with open(AUDIT_LOG_PATH, "a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


class Processor:
    """Event processor.

    ``kafka_bootstrap`` controls *where events come from*: ``None`` means no
    Kafka consumer is created (events are fed via ``process_event``), a list of
    brokers enables consumption in ``run()``.

    ``dry_run`` controls *whether Ansible really runs*: ``True`` prints the
    playbook invocation instead of executing it.
    """

    def __init__(self, kafka_bootstrap: Optional[List[str]] = None, topic: str = "telemetry.events",
                 dry_run: bool = True, connect_timeout_sec: int = KAFKA_CONNECT_TIMEOUT_SEC):
        self.dry_run = dry_run
        self.topic = topic
        self.kafka_bootstrap = kafka_bootstrap
        self.consume = kafka_bootstrap is not None
        self.consumer = None
        if self.consume:
            if KafkaConsumer is None:
                raise RuntimeError("kafka-python required for consumer mode (pip install kafka-python)")
            self.consumer = self._connect_consumer(connect_timeout_sec)
        self.store = SlidingStore()
        self.log_parser = LogParser()
        self.model = TriageModel()
        self.orchestrator = self._init_orchestrator()
        LOG.info("Processor initialized (dry_run=%s) kafka=%s topic=%s", self.dry_run, self.kafka_bootstrap, self.topic)

    def _connect_consumer(self, timeout_sec: int):
        """Create the consumer, retrying while the broker boots; raise KafkaUnavailable on timeout."""
        deadline = time.monotonic() + max(0, timeout_sec)
        attempt = 0
        while True:
            attempt += 1
            try:
                return KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.kafka_bootstrap,
                    auto_offset_reset="earliest",
                    group_id="processor-group",
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    api_version_auto_timeout_ms=5000,
                )
            except NoBrokersAvailable:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise KafkaUnavailable(KAFKA_START_HINT % self.kafka_bootstrap)
                LOG.warning("Kafka broker not ready (attempt %d); retrying for another %ds", attempt, int(remaining))
                time.sleep(min(3.0, remaining))

    @staticmethod
    def _init_orchestrator():
        """Build the AI orchestrator if the AI layer is available & enabled."""
        if get_orchestrator is None:
            return None
        try:
            cfg = get_ai_config() if get_ai_config else None
            if cfg is not None and not cfg.enabled:
                return None
            orch = get_orchestrator()
            LOG.info("AI multi-agent layer enabled (backend=%s)", orch.backend)
            return orch
        except Exception:
            LOG.exception("AI orchestrator init failed; continuing without AI layer")
            return None

    def correlate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Very simple correlation:
        - For each interface with errors on this host, check other hosts in recent window
        - Build correlated view for the controller
        """
        correlated = []
        for nic, stats in event.get("ifaces", {}).items():
            err_sum = int(stats.get("errin", 0)) + int(stats.get("errout", 0))
            if err_sum > 0:
                peers = self.store.hosts_with_iface_errors(nic, min_err=1)
                if peers:
                    correlated.append({"iface": nic, "hosts": list(set(peers + [event.get("host")]))})
        return {"correlated": correlated}

    def attempt_remediation(self, targets: List[Dict[str, Any]], playbook_name: str, extra_vars: Dict[str, Any], canary_first: bool = True) -> bool:
        """
        Orchestrates remediation:
        - if canary_first: apply playbook with --limit to first host; verify; then apply to rest.
        - uses controller.ansible_runner.run_playbook to execute
        - logs audit entries
        """
        if not targets:
            LOG.info("No targets to remediate")
            return False

        # ensure playbook exists
        playbook_path = os.path.join(PLAYBOOK_DIR, playbook_name)
        if not os.path.exists(playbook_path):
            LOG.error("Playbook not found: %s", playbook_path)
            return False

        # derive unique hosts list
        hosts = []
        for t in targets:
            hosts.append(t.get("host"))
        hosts = list(dict.fromkeys(hosts))  # preserve order, unique

        # prepare canary and remaining
        canary = hosts[0]
        remaining = hosts[1:]

        audit_entry = {"ts": iso_now(), "playbook": playbook_name, "targets": targets, "extra_vars": extra_vars, "status": "started"}
        audit_log(audit_entry)

        # run canary
        LOG.info("Running canary remediation on %s using %s", canary, playbook_path)
        ok = run_playbook(playbook_path, limit=canary, extra_vars=extra_vars, dry_run=self.dry_run)
        audit_entry = {"ts": iso_now(), "playbook": playbook_name, "phase": "canary", "host": canary, "ok": ok}
        audit_log(audit_entry)
        if not ok:
            LOG.error("Canary remediation failed on %s - attempting rollback (if rollback playbook exists)", canary)
            # attempt rollback playbook naming convention: rollback_<playbook_name>
            rb_playbook = os.path.join(PLAYBOOK_DIR, "rollback_" + playbook_name)
            if os.path.exists(rb_playbook):
                ok_rb = run_playbook(rb_playbook, limit=canary, extra_vars=extra_vars, dry_run=self.dry_run)
                audit_log({"ts": iso_now(), "rollback_playbook": rb_playbook, "host": canary, "ok": ok_rb})
            return False

        # apply to remaining hosts
        if remaining:
            LOG.info("Applying remediation to remaining hosts: %s", ", ".join(remaining))
            limit_arg = ",".join(remaining)
            ok2 = run_playbook(playbook_path, limit=limit_arg, extra_vars=extra_vars, dry_run=self.dry_run)
            audit_log({"ts": iso_now(), "playbook": playbook_path, "phase": "apply_remaining", "hosts": remaining, "ok": ok2})
            if not ok2:
                LOG.error("Remediation failed on remaining hosts; manual intervention required")
                return False

        LOG.info("Remediation completed successfully for playbook %s", playbook_name)
        audit_log({"ts": iso_now(), "playbook": playbook_path, "status": "completed"})
        return True

    def process_event(self, event: Dict[str, Any]):
        LOG.info("Processing event from host=%s id=%s", event.get("host"), event.get("event_id"))
        self.store.add(event)

        # Rule-based triage
        rule = rule_based_triage(event)

        # NLP parse logs
        dmesg = event.get("dmesg_tail", "")
        embedding = self.log_parser.embed_logs(dmesg)
        log_class = self.log_parser.classify_logs(dmesg)

        # ML triage
        ml_result = self.model.predict(event, embedding)

        # Correlation
        corr = self.correlate(event)

        decision = {"ts": iso_now(), "host": event.get("host"), "event_id": event.get("event_id"),
                    "rule": rule, "log_class": log_class, "ml": ml_result, "correlation": corr}
        LOG.info("Decision: %s", json.dumps(decision, indent=2))

        # AI multi-agent enrichment (RCA, remediation plan, risk). This augments
        # the deterministic decision; it never replaces the rule/ML remediation
        # path below, preserving backward compatibility.
        if self.orchestrator is not None:
            try:
                ai_result = self.orchestrator.run(
                    event,
                    {"rule": rule, "ml": ml_result, "log_class": log_class},
                )
                decision["ai"] = {
                    "incident_id": ai_result.get("incident_id"),
                    "llm_backend": ai_result.get("llm_backend"),
                    "rca": ai_result.get("rca"),
                    "remediation": ai_result.get("remediation"),
                    "context_sources": ai_result.get("context_sources", []),
                }
                audit_log({"ts": iso_now(), "event_id": event.get("event_id"),
                           "ai_incident": decision["ai"]})
            except Exception:
                LOG.exception("AI workflow failed for event %s", event.get("event_id"))


        # Decide to remediate if rule asks or ML predicts high priority
        should_remediate = False
        remediation_targets = []
        reason = ""
        if rule.get("action") == "remediate":
            should_remediate = True
            remediation_targets = rule.get("targets", [])
            reason = rule.get("reason", "")
        elif ml_result.get("priority_score", 0) >= 0.85:
            should_remediate = True
            # attempt to use model localization (if label is host or iface)
            loc = ml_result.get("localization")
            remediation_targets = [{"host": loc}] if loc else []
            reason = f"ML-priority:{ml_result.get('priority_score')}"
        else:
            LOG.info("No remediation triggered for event %s", event.get("event_id"))

        # trigger remediation if needed
        if should_remediate and remediation_targets:
            # choose playbook based on log_class / reason / target components
            playbook = select_playbook(reason, log_class, remediation_targets)

            extra_vars = {"targets": remediation_targets, "reason": reason, "ml_score": ml_result.get("priority_score", 0.0)}
            ok = self.attempt_remediation(remediation_targets, playbook, extra_vars)
            audit = {"decision": decision, "remediation_playbook": playbook, "remediation_ok": ok}
            audit_log(audit)
        else:
            audit_log({"ts": iso_now(), "event_id": event.get("event_id"), "action": "no_remediation", "ml_score": ml_result.get("priority_score", 0.0)})

        return decision

    def run(self):
        if not self.consume:
            LOG.info("Processor idle: no Kafka configured (use --kafka host:port). Ansible dry_run=%s", self.dry_run)
            while True:
                time.sleep(5)
        LOG.info("Consuming from Kafka %s topic=%s (Ansible dry_run=%s)", self.kafka_bootstrap, self.topic, self.dry_run)
        try:
            for msg in self.consumer:
                try:
                    self.process_event(msg.value)
                except Exception:
                    LOG.exception("Failed to process message")
        finally:
            self.consumer.close()


def parse_args():
    p = argparse.ArgumentParser("processor")
    p.add_argument("--kafka", help="Kafka bootstrap servers (comma separated); enables consumption", default=None)
    p.add_argument("--topic", help="Kafka topic", default="telemetry.events")
    p.add_argument("--dry-run", action="store_true", help="Simulate Ansible runs (Kafka consumption still happens if --kafka is set)")
    p.add_argument("--kafka-timeout", type=int, default=KAFKA_CONNECT_TIMEOUT_SEC,
                   help="Seconds to keep retrying the initial broker connection")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    bs = [s.strip() for s in args.kafka.split(",") if s.strip()] if args.kafka else None
    try:
        processor = Processor(kafka_bootstrap=bs, topic=args.topic, dry_run=args.dry_run,
                              connect_timeout_sec=args.kafka_timeout)
    except KafkaUnavailable as e:
        LOG.error("%s", e)
        return 1
    except RuntimeError as e:
        LOG.error("%s", e)
        return 2
    try:
        processor.run()
    except KeyboardInterrupt:
        LOG.info("Processor interrupted; shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
