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
except Exception:
    KafkaProducer = None

EVENT_TOPIC = "telemetry.events"


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


def run_dry(count: int):
    if not CONTROLLER_AVAILABLE:
        print("Controller modules not importable. Ensure repository root is on PYTHONPATH.")
        print("Attempting to run a light local validation (no controller).")
        for i in range(count):
            ev = make_synthetic_event(f"local-{i}", inject_error=(i % 2 == 0))
            print(json.dumps(ev, indent=2))
        return

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


def run_kafka(count: int, kafka_servers: str):
    if KafkaProducer is None:
        print("kafka-python not installed. Install requirements and try again.")
        return
    servers = kafka_servers.split(",")
    print(f"Connecting to Kafka at {servers}")
    producer = KafkaProducer(bootstrap_servers=servers, value_serializer=lambda v: json.dumps(v).encode("utf-8"))
    for i in range(count):
        ev = make_synthetic_event(f"kafka-vm-{i+1}", inject_error=(i % 2 == 0))
        print(f"Publishing event {ev['event_id']} host={ev['host']}")
        producer.send(EVENT_TOPIC, ev)
        producer.flush()
    print("Published all synthetic events.")


def run_localfile(count: int, dest: str):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    arr = []
    for i in range(count):
        arr.append(make_synthetic_event(f"file-vm-{i+1}", inject_error=(i % 2 == 0)))
    with open(dest, "w") as fh:
        json.dump(arr, fh, indent=2)
    print(f"Wrote {count} synthetic events to {dest}")


def parse_args():
    p = argparse.ArgumentParser(description="Validate network-bug-triage pipeline")
    p.add_argument("--mode", choices=["dry", "kafka", "localfile"], default="dry")
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--kafka", type=str, default="localhost:9092", help="Kafka bootstrap servers (comma separated)")
    p.add_argument("--outfile", type=str, default="data/sample_events.json")
    return p.parse_args()


def main():
    args = parse_args()
    if args.mode == "dry":
        run_dry(args.count)
    elif args.mode == "kafka":
        run_kafka(args.count, args.kafka)
    elif args.mode == "localfile":
        run_localfile(args.count, args.outfile)
    else:
        print("Unknown mode")

if __name__ == "__main__":
    main()
