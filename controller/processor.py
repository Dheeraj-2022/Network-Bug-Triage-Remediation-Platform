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

Usage (dry-run):
    python3 controller/processor.py --dry-run

Usage (Kafka):
    python3 controller/processor.py --kafka localhost:9092

Notes:
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
from controller.rules_engine import rule_based_triage
from controller.nlp_parser import LogParser
from controller.triage_model import TriageModel
from controller.ansible_runner import run_playbook

# kafka import guarded
try:
    from kafka import KafkaConsumer
except Exception:
    KafkaConsumer = None

LOG = logging.getLogger("nbt.processor")
LOG.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
LOG.addHandler(_handler)

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "remediation_audit.log")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "xgb_model.joblib")
PLAYBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "infra", "playbooks")


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
        return [e for e in self.events if datetime.fromisoformat(e["ts"]).timestamp() >= cutoff]

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
    def __init__(self, kafka_bootstrap: Optional[List[str]] = None, topic: str = "telemetry.events", dry_run: bool = True):
        self.dry_run = dry_run
        self.topic = topic
        self.kafka_bootstrap = kafka_bootstrap or ["localhost:9092"]
        self.consumer = None
        if not dry_run:
            if KafkaConsumer is None:
                raise RuntimeError("kafka-python required for consumer mode")
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.kafka_bootstrap,
                auto_offset_reset="earliest",
                group_id="processor-group",
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
        self.store = SlidingStore()
        self.log_parser = LogParser()
        self.model = TriageModel()
        LOG.info("Processor initialized (dry_run=%s) kafka=%s topic=%s", self.dry_run, self.kafka_bootstrap, self.topic)

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
            # choose playbook based on log_class or reason
            playbook = None
            if any('mtu' in reason.lower() or log_class == "MTU_MISMATCH" for _ in [0]):
                playbook = "remediate_mtu.yml"
            elif log_class == "DRIVER_FAULT" or any(t.get("component") == "rdma_qp" for t in remediation_targets):
                playbook = "restart_driver.yml"
            else:
                playbook = "remediate_mtu.yml"

            extra_vars = {"targets": remediation_targets, "reason": reason, "ml_score": ml_result.get("priority_score", 0.0)}
            ok = self.attempt_remediation(remediation_targets, playbook, extra_vars)
            audit = {"decision": decision, "remediation_playbook": playbook, "remediation_ok": ok}
            audit_log(audit)
        else:
            audit_log({"ts": iso_now(), "event_id": event.get("event_id"), "action": "no_remediation", "ml_score": ml_result.get("priority_score", 0.0)})

        return decision

    def run(self):
        if self.dry_run:
            LOG.info("Processor running in dry-run mode (no Kafka consumption). Use --kafka to enable")
            while True:
                time.sleep(5)
        else:
            LOG.info("Connecting to Kafka: %s", self.kafka_bootstrap)
            for msg in self.consumer:
                try:
                    self.process_event(msg.value)
                except Exception:
                    LOG.exception("Failed to process message")


def parse_args():
    p = argparse.ArgumentParser("processor")
    p.add_argument("--kafka", help="Kafka bootstrap servers (comma separated)", default=None)
    p.add_argument("--topic", help="Kafka topic", default="telemetry.events")
    p.add_argument("--dry-run", action="store_true", help="Dry-run (no Kafka/Ansible runs)")
    return p.parse_args()


def main():
    args = parse_args()
    bs = args.kafka.split(",") if args.kafka else None
    processor = Processor(kafka_bootstrap=bs, topic=args.topic, dry_run=args.dry_run)
    processor.run()


if __name__ == "__main__":
    main()
