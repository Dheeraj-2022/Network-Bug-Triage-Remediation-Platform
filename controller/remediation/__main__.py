#!/usr/bin/env python3
"""
Operator CLI for remediation proposals (used for the Kafka/processor path, which
has no UI of its own). Shares the SQLite store with the API.

    python -m controller.remediation list
    python -m controller.remediation show <id>
    python -m controller.remediation approve <id> --approver alice [--digest <preview_digest>]
    python -m controller.remediation reject  <id> --approver alice --reason "wrong host"
    python -m controller.remediation verify  <id> --samples post_samples.json

Execution mode comes from NBT_REMEDIATION_MODE (default: simulate).
"""

import argparse
import json
import sys

from controller.remediation import RemediationPolicy


def main(argv=None) -> int:
    p = argparse.ArgumentParser("controller.remediation")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").add_argument("--limit", type=int, default=20)
    sub.add_parser("show").add_argument("id")
    for name in ("approve", "reject"):
        sp = sub.add_parser(name)
        sp.add_argument("id")
        sp.add_argument("--approver", required=True)
        sp.add_argument("--digest", help="preview_digest you reviewed (recommended)")
        sp.add_argument("--reason")
    vp = sub.add_parser("verify")
    vp.add_argument("id")
    vp.add_argument("--samples", required=True, help="JSON file with a list of post-change telemetry events")
    args = p.parse_args(argv)

    policy = RemediationPolicy()
    if args.cmd == "list":
        for r in policy.list(limit=args.limit):
            prev = r.get("preview") or {}
            print(f"{r['id']}  {r['status']:<26} {prev.get('action') or '-':<18} "
                  f"{','.join(prev.get('limit') or []) or r.get('host')}  mode={r['mode']}")
        return 0
    if args.cmd == "show":
        r = policy.get(args.id)
        print(json.dumps(r, indent=2) if r else "not found")
        return 0 if r else 1
    if args.cmd in ("approve", "reject"):
        res, code = policy.decide(args.id, approved=args.cmd == "approve", approver=args.approver,
                                  preview_digest=args.digest, reason=args.reason)
    else:
        with open(args.samples, encoding="utf-8") as fh:
            samples = json.load(fh)
        res, code = policy.verify(args.id, samples if isinstance(samples, list) else [samples])
    print(json.dumps(res, indent=2, default=str))
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
