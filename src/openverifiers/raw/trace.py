"""OVTrace data model and its JSON-lines form.

A trace is the evaluator's *claimed* derivation: an ordered list of steps.
Each fired step records the head atom's cumulative label after the firing,
the atom's previous step (``prev``), the premise steps it used (all earlier
in the trace), and for closed-world negation the step holding the negated
atom's final label (or ``None``: never derived). The checker re-verifies all
of it; nothing here is believed.

Trusted code (only because the checker parses traces with it).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from .labels import Env, Label, label_key
from .program import Atom, Span
from .terms import Term
from .text import dump_atom, dump_term, parse_atom, parse_term

STEP_KINDS = ("fired", "blocked")
BLOCK_REASONS = ("budget", "missing", "naf_failed", "builtin_failed")


@dataclass(frozen=True, slots=True)
class NafRef:
    atom: Atom
    step: int | None


@dataclass(frozen=True, slots=True)
class Step:
    id: int
    kind: str
    rule_id: str
    conclusion: Atom
    label: Label
    stratum: int
    subst: tuple[tuple[str, Term], ...] = ()
    premises: tuple[int, ...] = ()
    naf: tuple[NafRef, ...] = ()
    prev: int | None = None
    span: Span | None = None
    reason: str = ""  # for blocked steps


@dataclass(frozen=True, slots=True)
class Trace:
    steps: tuple[Step, ...]
    strata: tuple[tuple[str, int], ...]
    complete: tuple[bool, ...]          # per stratum index
    truncated: frozenset[Atom] = frozenset()


# --------------------------------------------------------------------------- JSON


def label_to_json(lab: Label) -> list[list[str]]:
    return [[n if s else "~" + n for n, s in k] for _, k in label_key(lab)]


def label_from_json(data: object) -> Label:
    if not isinstance(data, list):
        raise ValueError("label must be a list of environments")
    envs: list[Env] = []
    for env in data:
        if not isinstance(env, list) or not all(isinstance(x, str) for x in env):
            raise ValueError("environment must be a list of strings")
        envs.append(frozenset((x[1:], False) if x.startswith("~") else (x, True) for x in env))
    return frozenset(envs)


def _span_json(s: Span | None) -> list[object] | None:
    return None if s is None else [s.file, s.line, s.col, s.end_line, s.end_col]


def step_to_json(s: Step) -> dict[str, object]:
    d: dict[str, object] = {
        "id": s.id, "kind": s.kind, "rule_id": s.rule_id,
        "subst": {k: dump_term(v) for k, v in s.subst},
        "premises": list(s.premises),
        "naf": [{"atom": dump_atom(n.atom), "step": n.step} for n in s.naf],
        "prev": s.prev, "conclusion": dump_atom(s.conclusion),
        "label": label_to_json(s.label), "stratum": s.stratum,
        "source_span": _span_json(s.span),
    }
    if s.reason:
        d["reason"] = s.reason
    return d


def dumps(trace: Trace) -> str:
    header = {"kind": "header", "strata": dict(trace.strata), "complete": list(trace.complete),
              "truncated": sorted(dump_atom(a) for a in trace.truncated)}
    lines = [json.dumps(header, sort_keys=True)]
    lines += [json.dumps(step_to_json(s), sort_keys=True) for s in trace.steps]
    return "\n".join(lines) + "\n"


def _int_or_none(x: object) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"expected an integer step id, got {x!r}")
    return x


def step_from_json(d: dict[str, object]) -> Step:
    subst = d.get("subst", {})
    premises = d.get("premises", [])
    naf = d.get("naf", [])
    span = d.get("source_span")
    if not isinstance(subst, dict) or not isinstance(premises, list) or not isinstance(naf, list):
        raise ValueError("malformed step")
    sid, stratum = _int_or_none(d.get("id")), _int_or_none(d.get("stratum"))
    if sid is None or stratum is None:
        raise ValueError("step needs id and stratum")
    naf_refs = []
    for n in naf:
        if not isinstance(n, dict):
            raise ValueError("malformed naf reference")
        naf_refs.append(NafRef(parse_atom(str(n["atom"])), _int_or_none(n.get("step"))))
    span_v = None
    if isinstance(span, list) and len(span) == 5:
        f, a, b, c, e = span
        span_v = Span(str(f), int(str(a)), int(str(b)), int(str(c)), int(str(e)))
    return Step(
        id=sid, kind=str(d["kind"]), rule_id=str(d["rule_id"]),
        conclusion=parse_atom(str(d["conclusion"])), label=label_from_json(d["label"]),
        stratum=stratum,
        subst=tuple(sorted((str(k), parse_term(str(v))) for k, v in subst.items())),
        premises=tuple(p for x in premises if (p := _int_or_none(x)) is not None),
        naf=tuple(naf_refs), prev=_int_or_none(d.get("prev")), span=span_v,
        reason=str(d.get("reason", "")),
    )


def loads(text: str | Iterable[str]) -> Trace:
    lines = text.splitlines() if isinstance(text, str) else list(text)
    rows = [json.loads(x) for x in lines if x.strip()]
    if not rows or rows[0].get("kind") != "header":
        raise ValueError("trace must start with a header line")
    h = rows[0]
    return Trace(
        steps=tuple(step_from_json(r) for r in rows[1:]),
        strata=tuple(sorted((str(k), int(v)) for k, v in h["strata"].items())),
        complete=tuple(bool(x) for x in h["complete"]),
        truncated=frozenset(parse_atom(a) for a in h["truncated"]),
    )
