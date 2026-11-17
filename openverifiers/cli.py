"""Command line: ``ov check | trace | solve | bench run | demo repair``.

Exit codes: 0 valid, 1 rejected, 2 the input file is malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import cast

from openverifiers.case import Case, load_case
from openverifiers.domains import PACKS, load
from openverifiers.kernel import TRACE_FILTERS, FormatError, check, proof_to_dict, verdict_to_dict
from openverifiers.kernel.serialize import TraceFilter


def _load(path: str) -> Case:
    try:
        return load_case(path)
    except (FormatError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _verdict(case: Case, mode: TraceFilter) -> int:
    v = check(case.facts, case.requirements, case.proof, load(case.domain))
    print(json.dumps(verdict_to_dict(v, mode), indent=2))
    return 0 if v.valid else 1


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ov", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="check a case's candidate proof; print the verdict")
    p.add_argument("case")
    p = sub.add_parser("trace", help="print the verdict with a filtered trace")
    p.add_argument("case")
    p.add_argument("--filter", choices=TRACE_FILTERS, default="full")
    p = sub.add_parser("solve", help="ignore the candidate proof; propose one and check it")
    p.add_argument("case")
    p.add_argument("--proposer", choices=("forward", "backward"), default="forward")
    p = sub.add_parser("bench", help="mutation benchmark")
    p.add_argument("action", choices=("run",))
    p.add_argument("--domain", action="append", choices=sorted(PACKS))
    p = sub.add_parser("demo", help="demos")
    p.add_argument("name", choices=("repair",))
    p.add_argument("--log", help="write every attempt as JSON lines to this file")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return _verdict(_load(args.case), "failure_trail")
    if args.cmd == "trace":
        return _verdict(_load(args.case), cast(TraceFilter, args.filter))
    if args.cmd == "solve":
        from openverifiers.proposers import BackwardDecomposer, ForwardChainer, ProposalError
        case = _load(args.case)
        pack = load(case.domain)
        proposer = ForwardChainer() if args.proposer == "forward" else BackwardDecomposer()
        try:
            proof = proposer.propose(case.facts, case.requirements, pack)
        except ProposalError as exc:
            print(f"proposer failed: {exc}", file=sys.stderr)
            return 1
        v = check(case.facts, case.requirements, proof, pack)
        print(json.dumps({"proof": proof_to_dict(proof),
                          "verdict": verdict_to_dict(v, "failure_trail")}, indent=2))
        return 0 if v.valid else 1
    if args.cmd == "bench":
        from benchmarks.run import main as bench_main
        print(bench_main(args.domain or sorted(PACKS)))
        return 0
    if args.cmd == "demo":
        from openverifiers.demo import run_repair_demo
        result, lines = run_repair_demo(args.log)
        print("\n".join(lines))
        return 0 if result.accepted else 1
    return 2  # unreachable: argparse enforces the subcommands


if __name__ == "__main__":
    raise SystemExit(main())
