"""KDScript-Proof: agent-facing trace language -> TraceStep list.

v1 syntax is the closed trace DSL (documented in docs/kerscript/proof-language.md),
optionally wrapped in a named block:

    proof <name>:
        z = math.mul(a, b)
        assume H: claim text
        step = math.proof_step(predecessor=base) with k=0, expr="2n-1"
        end contradiction
        # comments allowed anywhere

The parser strips the optional header, then delegates to the closed
`parse_dsl` — the same schema, the same whitelist discipline, zero
code-execution paths. A KDScript-Proof document is NOT Turing-complete: it
names registered transformations, supplies inputs/params, and opens/closes
assumption scopes; nothing else.
"""
from __future__ import annotations

import re

from openverifiers.v2 import TraceStep, parse_dsl

_HEADER = re.compile(r"^\s*proof\s+([A-Za-z_][\w]*)\s*:\s*$")


def parse_proof(text: str) -> tuple[str, list[TraceStep]]:
    lines = text.splitlines()
    name = ""
    body = text
    first = next((ln for ln in lines if ln.strip()), "")
    if _HEADER.match(first):
        name = _HEADER.match(first).group(1)
        rest = lines[1:]
        depth = 0
        kept: list[str] = []
        for ln in rest:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if depth == 0:
                # a top-level non-step line after the header is malformed
                if not _looks_like_step(s):
                    raise ValueError(f"cannot parse proof step: {ln!r}")
            kept.append(ln)
        body = "\n".join(kept)
    return name, parse_dsl(body)


def _looks_like_step(line: str) -> bool:
    return (line.startswith("assume ") or line.startswith("end")
            or "=" in line)