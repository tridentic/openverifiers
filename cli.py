#!/usr/bin/env python3
"""OpenVerifiers — CLI (thin wrapper over the SDK, per ARCHITECTURE.md §7.2).

Usage:
    python -m openverifiers.cli "A car starts from rest and accelerates at 2 m/s^2 for 5 s. Find its final velocity."
    python -m openverifiers.cli --view full "A car travels 100 m in 10 s at constant velocity. Find its speed."
    python -m openverifiers.cli --explicit initial_velocity=0,acceleration=9.8 "A stone is dropped from a cliff. Find its velocity after 3 s."
    python -m openverifiers.cli --json "..."
"""

from __future__ import annotations

import argparse
import json
import sys

from . import verify_physics


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="openverifiers", description="Verify AI agent claims with deterministic, traceable reasoning (physics slice).")
    ap.add_argument("problem", nargs="?", help="physics word problem")
    ap.add_argument("--view", choices=("success-path", "failure-trail", "full"), default="success-path")
    ap.add_argument("--explicit", default="", help="comma k=v overrides, e.g. initial_velocity=0,acceleration=9.8")
    ap.add_argument("--target", default=None, help="explicit target kind")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    if not args.problem:
        ap.print_help()
        return 1

    explicit = {}
    for kv in filter(None, args.explicit.split(",")):
        k, _, v = kv.partition("=")
        explicit[k.strip()] = v.strip()

    result = verify_physics(args.problem, explicit=explicit or None,
                            explicit_target=args.target)

    if args.json:
        print(json.dumps({
            "status": result.status,
            "answer": str(result.answer) if result.answer is not None else None,
            "target": result.target,
            "trace": {v: len(getattr(result, v)) for v in ("success_path", "failure_trail", "full")},
        }, indent=2))
        return 0

    print(result.render(args.view))
    return 0


if __name__ == "__main__":
    sys.exit(main())