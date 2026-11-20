#!/usr/bin/env python3
"""
Controller Processor (full)

- Consumes from Kafka (topic: telemetry.events) or runs in dry-run
- Runs rule-based triage (rules_engine)
- Creates log embeddings & classifies logs (nlp_parser)
- Runs ML triage (triage_model)
- Correlates recent events in-memory and builds topology-aware evidence
- Submits remediation candidates to the shared RemediationPolicy, which only
  previews them; execution happens after human approval
  (`python -m controller.remediation approve <id> --approver <name>` or the API)
- Audit logs triage decisions and proposals

Usage (dry-run, no Kafka - idle until killed; use tests/validate_pipeline.py --mode dry to feed events):
    python3 controller/processor.py --dry-run

Usage (Kafka, proposals bound to simulation mode):
    python3 controller/processor.py --kafka localhost:9092 --dry-run

Usage (Kafka, proposals bound to REAL Ansible execution after approval; explicit opt-in):
    python3 controller/processor.py --kafka localhost:9092 --execute

Notes:
- The processor never runs Ansible itself. Approved proposals execute in the
  mode recorded at preview time; the approving process must run in the same mode.
- Without --dry-run/--execute the mode comes from NBT_REMEDIATION_MODE (default: simulate).
"""
import argparse
import json
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# local imports (should exist from Phase 2)
from controller.rules_engine import rule_based_triage
from controller.nlp_parser import LogParser
from controller.triage_model import TriageModel
from controller.evidence import build_evidence
from controller.remediation import RemediationPolicy, summarize
from controller.remediation.candidates import build_candidates

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
KAFKA_CONNECT_TIMEOUT_SEC = int(os.environ.get("NBT_KAFKA_CONNECT_TIMEOUT", "60"))
KAFKA_START_HINT = ("No Kafka broker reachable at %s. Start one with `docker compose up -d` "
                    "and wait for it to finish booting, or fix --kafka host:port.")


class KafkaUnavailable(RuntimeError):
    """Raised when no broker could be reached within the connect timeout."""


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def _ts(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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

    def context_for(self, event: Dict[str, Any]):
        """Previous sample from the same host and the latest sample of every other host."""
        previous, latest = None, {}
        for e in self.events:
            if e is event:
                continue
            if e.get("host") == event.get("host"):
                t0, t1 = _ts(e.get("ts")), _ts(event.get("ts"))
                if t0 and t1 and t0 < t1:
                    previous = e
            elif e.get("host"):
                latest[e["host"]] = e
        return previous, list(latest.values())


def audit_log(entry: Dict[str, Any]):
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    with open(AUDIT_LOG_PATH, "a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


class Processor:
    """Event processor.

    ``kafka_bootstrap`` controls *where events come from*: ``None`` means no
    Kafka consumer is created (events are fed via ``process_event``), a list of
    brokers enables consumption in ``run()``.

    ``dry_run=True`` binds every proposal to simulation mode (no infrastructure
    change, even after approval). ``mode`` (``simulate``/``ansible``) or
    NBT_REMEDIATION_MODE applies otherwise. Either way the processor itself
    never executes a playbook: all remediation goes through the shared policy.
    """

    def __init__(self, kafka_bootstrap: Optional[List[str]] = None, topic: str = "telemetry.events",
                 dry_run: bool = True, connect_timeout_sec: int = KAFKA_CONNECT_TIMEOUT_SEC,
                 mode: Optional[str] = None, policy: Optional[RemediationPolicy] = None,
                 enable_ai: bool = True):
        self.dry_run = dry_run
        self.topic = topic
        self.kafka_bootstrap = kafka_bootstrap
        self.consume = kafka_bootstrap is not None
        self.consumer = None
        self.policy = policy or RemediationPolicy(mode="simulate" if dry_run else mode)
        if self.consume:
            if KafkaConsumer is None:
                raise RuntimeError("kafka-python required for consumer mode (pip install kafka-python)")
            self.consumer = self._connect_consumer(connect_timeout_sec)
        self.store = SlidingStore()
        self.log_parser = LogParser()
        self.model = TriageModel()
        self.orchestrator = self._init_orchestrator() if enable_ai else None
        LOG.info("Processor initialized (remediation mode=%s) kafka=%s topic=%s",
                 self.policy.mode, self.kafka_bootstrap, self.topic)

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

    def process_event(self, event: Dict[str, Any]):
        LOG.info("Processing event from host=%s id=%s", event.get("host"), event.get("event_id"))
        previous, peers = self.store.context_for(event)
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

        evidence = build_evidence(event, self.policy.registry, previous=previous, peer_samples=peers,
                                  rule=rule, log_class=log_class)
        decision = {"ts": iso_now(), "host": event.get("host"), "event_id": event.get("event_id"),
                    "rule": rule, "log_class": log_class, "ml": ml_result, "correlation": corr,
                    "evidence": evidence}
        LOG.info("Decision for %s: rule=%s log_class=%s diagnosis=%s (%s)", event.get("event_id"),
                 rule.get("action"), log_class, evidence["inference"]["fault_domain"],
                 evidence["confidence"]["level"])

        # AI multi-agent enrichment (RCA, remediation plan, risk). Its plan is only
        # a candidate for the shared policy below; it cannot execute anything.
        ai_remediation = None
        if self.orchestrator is not None:
            try:
                ai_result = self.orchestrator.run(
                    event,
                    {"rule": rule, "ml": ml_result, "log_class": log_class},
                )
                ai_remediation = ai_result.get("remediation")
                decision["ai"] = {
                    "incident_id": ai_result.get("incident_id"),
                    "llm_backend": ai_result.get("llm_backend"),
                    "rca": ai_result.get("rca"),
                    "remediation": ai_remediation,
                    "context_sources": ai_result.get("context_sources", []),
                }
                audit_log({"ts": iso_now(), "event_id": event.get("event_id"),
                           "ai_incident": decision["ai"]})
            except Exception:
                LOG.exception("AI workflow failed for event %s", event.get("event_id"))

        candidates = build_candidates(rule, ml_result, log_class, ai_remediation)
        if candidates:
            proposal = self.policy.propose(source="processor", event=event, evidence=evidence,
                                           candidates=candidates,
                                           incident_ref=(decision.get("ai") or {}).get("incident_id")
                                           or event.get("event_id"))
            decision["remediation"] = summarize(proposal)
            audit_log({"ts": iso_now(), "event_id": event.get("event_id"), "action": "remediation_proposed",
                       "remediation": decision["remediation"]})
            if proposal["status"] == "pending_approval":
                LOG.info("Proposal %s awaits approval (mode=%s): python -m controller.remediation approve %s "
                         "--approver <name> --digest %s", proposal["id"], proposal["mode"], proposal["id"],
                         proposal["preview_digest"])
            else:
                LOG.info("Proposal %s is %s: %s", proposal["id"], proposal["status"], proposal.get("block_reason"))
        else:
            LOG.info("No remediation triggered for event %s", event.get("event_id"))
            audit_log({"ts": iso_now(), "event_id": event.get("event_id"), "action": "no_remediation",
                       "ml_score": ml_result.get("priority_score", 0.0)})

        return decision

    def run(self):
        if not self.consume:
            LOG.info("Processor idle: no Kafka configured (use --kafka host:port). Remediation mode=%s",
                     self.policy.mode)
            while True:
                time.sleep(5)
        LOG.info("Consuming from Kafka %s topic=%s (remediation mode=%s)", self.kafka_bootstrap, self.topic,
                 self.policy.mode)
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
    p.add_argument("--dry-run", action="store_true",
                   help="Bind proposals to simulation mode: nothing is changed even after approval "
                        "(Kafka consumption still happens if --kafka is set)")
    p.add_argument("--execute", action="store_true",
                   help="Explicit opt-in: bind proposals to real Ansible execution after human approval")
    p.add_argument("--kafka-timeout", type=int, default=KAFKA_CONNECT_TIMEOUT_SEC,
                   help="Seconds to keep retrying the initial broker connection")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run and args.execute:
        LOG.error("--dry-run and --execute are mutually exclusive")
        return 2
    bs = [s.strip() for s in args.kafka.split(",") if s.strip()] if args.kafka else None
    try:
        processor = Processor(kafka_bootstrap=bs, topic=args.topic, dry_run=args.dry_run,
                              connect_timeout_sec=args.kafka_timeout,
                              mode="ansible" if args.execute else None)
    except KafkaUnavailable as e:
        LOG.error("%s", e)
        return 1
    except (RuntimeError, ValueError) as e:
        LOG.error("%s", e)
        return 2
    try:
        processor.run()
    except KeyboardInterrupt:
        LOG.info("Processor interrupted; shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
