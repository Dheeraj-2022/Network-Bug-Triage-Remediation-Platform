#!/usr/bin/env python3
"""
tests/validate_pipeline.py

Simple validator for the network-bug-triage pipeline.

Modes:
  - dry (default): runs Processor in dry-run and calls process_event on generated synthetic events
  - kafka: publishes synthetic events to Kafka topic (requires running Kafka)
  - localfile: write events to data/sample_events.json

Usage:
  python3 tests/validate_pipeline.py --mode dry --count 3
  python3 tests/validate_pipeline.py --mode kafka --kafka localhost:9092 --count 5
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import List

# attempt to import controller. If package imports fail, adjust sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from controller.processor import Processor
    from controller.nlp_parser import LogParser
    from controller.triage_model import TriageModel
    CONTROLLER_AVAILABLE = True
except Exception:
    CONTROLLER_AVAILABLE = False

try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError, NoBrokersAvailable
except Exception:
    KafkaProducer = None
    KafkaError = NoBrokersAvailable = Exception

EVENT_TOPIC = "telemetry.events"
KAFKA_START_HINT = (
    "No Kafka broker reachable. Start one with `docker compose up -d` (ZooKeeper + Kafka on "
    "localhost:9092) and wait ~20s for the broker to finish booting, or pass --kafka host:port."
)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def make_synthetic_event(host: str, inject_error: bool = False):
    """
    Create a synthetic telemetry event.
    If inject_error=True, create an iface error or RDMA error to trigger triage.
    """
    ifaces = {
        "eth0": {
            "rx_bytes": random.randint(1000, 1000000),
            "tx_bytes": random.randint(1000, 1000000),
            "errin": 0,
            "errout": 0,
            "mtu": 1500
        },
        "eth1": {
            "rx_bytes": random.randint(1000, 1000000),
            "tx_bytes": random.randint(1000, 1000000),
            "errin": 0,
            "errout": 0,
            "mtu": 1500
        }
    }
    rdma = {"qp_errors": 0, "rq_errors": 0, "srq_errors": 0}

    dmesg = "Normal boot messages"

    if inject_error:
        # randomly choose a fault type
        fault = random.choice(["mtu", "iface_err", "rdma", "driver"])
        if fault == "iface_err":
            ifaces["eth0"]["errout"] = random.randint(6, 20)
            dmesg = "eth0: TX errors detected; driver reports packet drop"
        elif fault == "mtu":
            ifaces["eth0"]["mtu"] = random.choice([1400, 9000])  # set mismatch
            dmesg = "eth0: MTU mismatch detected"
        elif fault == "rdma":
            rdma["qp_errors"] = random.randint(1, 5)
            dmesg = "mlx5_core: RDMA QP reset or qp error"
        elif fault == "driver":
            dmesg = "driver: kernel oops - stack trace ..."

    ev = {
        "event_id": f"synthetic-{host}-{int(time.time())}-{random.randint(1,10000)}",
        "host": host,
        "ts": iso_now(),
        "ifaces": ifaces,
        "rdma": rdma,
        "dmesg_tail": dmesg,
        "sample_packets": [{"src": "10.0.0.1", "dst": "10.0.0.2", "len": 128, "proto": "TCP"}]
    }
    return ev


def run_dry(count: int) -> int:
    if not CONTROLLER_AVAILABLE:
        print("Controller modules not importable. Ensure repository root is on PYTHONPATH.")
        print("Attempting to run a light local validation (no controller).")
        for i in range(count):
            ev = make_synthetic_event(f"local-{i}", inject_error=(i % 2 == 0))
            print(json.dumps(ev, indent=2))
        return 1

    proc = Processor(dry_run=True)
    successes = 0
    for i in range(count):
        ev = make_synthetic_event(f"vm-{i+1}", inject_error=(i % 2 == 0))
        print(f"\n--- Processing synthetic event {i+1}/{count} host={ev['host']} inject_error={(i%2==0)} ---")
        dec = proc.process_event(ev)
        # basic validation
        if dec.get("rule", {}).get("action") == "remediate" or dec.get("ml", {}).get("priority_score", 0) > 0.5:
            successes += 1
    print(f"\nDry-run validation: {successes}/{count} events caused remediation or high-priority ML score.")
    return 0


def connect_producer(servers: List[str], wait_sec: int):
    """Connect to Kafka, retrying until ``wait_sec`` elapses (broker may still be booting)."""
    deadline = time.monotonic() + max(0, wait_sec)
    attempt = 0
    while True:
        attempt += 1
        try:
            return KafkaProducer(
                bootstrap_servers=servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                api_version_auto_timeout_ms=5000,
                request_timeout_ms=10000,
                max_block_ms=10000,
            )
        except NoBrokersAvailable:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            print(f"  broker not ready (attempt {attempt}); retrying for another {int(remaining)}s ...")
            time.sleep(min(3, remaining))


def run_kafka(count: int, kafka_servers: str, wait_sec: int, topic: str) -> int:
    if KafkaProducer is None:
        print("kafka-python not installed. Install requirements and try again.")
        return 2
    servers = [s.strip() for s in kafka_servers.split(",") if s.strip()]
    print(f"Connecting to Kafka at {servers}")
    producer = connect_producer(servers, wait_sec)
    if producer is None:
        print(f"ERROR: {KAFKA_START_HINT}")
        return 1
    published = 0
    try:
        for i in range(count):
            ev = make_synthetic_event(f"kafka-vm-{i+1}", inject_error=(i % 2 == 0))
            print(f"Publishing event {ev['event_id']} host={ev['host']}")
            meta = producer.send(topic, ev).get(timeout=15)
            print(f"  -> {meta.topic}[{meta.partition}] offset={meta.offset}")
            published += 1
        producer.flush()
    except KafkaError as e:
        print(f"ERROR: publish failed after {published}/{count} events: {e}")
        return 1
    finally:
        producer.close()
    print(f"Published all {published} synthetic events to topic '{topic}'.")
    print("Consume them with: python -m controller.processor --kafka "
          f"{kafka_servers} --dry-run")
    return 0


def run_localfile(count: int, dest: str) -> int:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    arr = []
    for i in range(count):
        arr.append(make_synthetic_event(f"file-vm-{i+1}", inject_error=(i % 2 == 0)))
    with open(dest, "w") as fh:
        json.dump(arr, fh, indent=2)
    print(f"Wrote {count} synthetic events to {dest}")
    return 0


def parse_args():
    p = argparse.ArgumentParser(description="Validate network-bug-triage pipeline")
    p.add_argument("--mode", choices=["dry", "kafka", "localfile"], default="dry")
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--kafka", type=str, default="localhost:9092", help="Kafka bootstrap servers (comma separated)")
    p.add_argument("--topic", type=str, default=EVENT_TOPIC, help="Kafka topic to publish to")
    p.add_argument("--wait", type=int, default=30,
                   help="Seconds to keep retrying the Kafka connection while the broker boots")
    p.add_argument("--outfile", type=str, default="data/sample_events.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "dry":
        return run_dry(args.count)
    if args.mode == "kafka":
        return run_kafka(args.count, args.kafka, args.wait, args.topic)
    if args.mode == "localfile":
        return run_localfile(args.count, args.outfile)
    print("Unknown mode")
    return 2


if __name__ == "__main__":
    sys.exit(main())
