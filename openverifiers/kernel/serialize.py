"""JSON <-> kernel model, plus verdict/trace rendering.

Parsing is strict: unknown keys and wrong shapes raise ``FormatError``.
Semantic problems (duplicate ids, cycles, ...) are *not* format errors; they
parse fine and are reported by ``check`` as failures, so they show up in the
trace like any other rejection.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, Literal, cast

from .model import (
    FACT_STATUSES,
    Fact,
    FactStatus,
    Failure,
    Proof,
    Provenance,
    Requirement,
    Selector,
    Step,
    TraceEvent,
    Verdict,
)

TraceFilter = Literal["full", "success_path", "failure_trail"]
TRACE_FILTERS: tuple[TraceFilter, ...] = ("full", "success_path", "failure_trail")


class FormatError(ValueError):
    """The JSON does not have the shape of a fact, requirement, or proof."""


def _obj(d: Any, where: str, required: set[str], optional: set[str]) -> dict[str, Any]:
    if not isinstance(d, dict):
        raise FormatError(f"{where}: expected an object, got {type(d).__name__}")
    keys = set(d)
    if missing := required - keys:
        raise FormatError(f"{where}: missing keys {sorted(missing)}")
    if extra := keys - required - optional:
        raise FormatError(f"{where}: unknown keys {sorted(extra)}")
    return d


def _str(v: Any, where: str) -> str:
    if not isinstance(v, str) or not v:
        raise FormatError(f"{where}: expected a non-empty string")
    return v


def _map(v: Any, where: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise FormatError(f"{where}: expected an object")
    return v


def _list(v: Any, where: str) -> list[Any]:
    if not isinstance(v, list):
        raise FormatError(f"{where}: expected a list")
    return v


def fact_from_dict(d: Any, where: str = "fact") -> Fact:
    d = _obj(d, where, {"id", "type"}, {"value", "unit", "owner", "status", "attributes",
                                        "children", "provenance", "why_unknown",
                                        "evidence_needed"})
    fid = _str(d["id"], f"{where}.id")
    status = d.get("status", "truth")
    if status not in FACT_STATUSES:
        raise FormatError(f"{where} {fid!r}: status must be one of {FACT_STATUSES}")
    prov = None
    if d.get("provenance") is not None:
        p = _obj(d["provenance"], f"{where}.provenance", {"source"}, {"citation"})
        prov = Provenance(source=_str(p["source"], "provenance.source"),
                          citation=p.get("citation"))
    return Fact(
        id=fid,
        type=_str(d["type"], f"{where}.type"),
        value=d.get("value"),
        unit=d.get("unit"),
        owner=d.get("owner"),
        status=cast(FactStatus, status),
        attributes=_map(d.get("attributes", {}), f"{where}.attributes"),
        children=tuple(fact_from_dict(c, f"{where}.children[{i}]")
                       for i, c in enumerate(_list(d.get("children", []), f"{where}.children"))),
        provenance=prov,
        why_unknown=d.get("why_unknown"),
        evidence_needed=tuple(_list(d.get("evidence_needed", []), f"{where}.evidence_needed")),
    )


def requirement_from_dict(d: Any, where: str = "requirement") -> Requirement:
    d = _obj(d, where, {"id"}, {"fact_id", "where", "predicate", "args"})
    if ("fact_id" in d) == ("where" in d):
        raise FormatError(f"{where}: give exactly one of fact_id or where")
    return Requirement(
        id=_str(d["id"], f"{where}.id"),
        selector=Selector(fact_id=d.get("fact_id"), where=_map(d.get("where", {}), where)),
        predicate=_str(d.get("predicate", "exists"), f"{where}.predicate"),
        args=_map(d.get("args", {}), f"{where}.args"),
    )


def step_from_dict(d: Any, where: str = "step") -> Step:
    d = _obj(d, where, {"id", "transformation"}, {"inputs", "outputs", "params"})
    inputs = _map(d.get("inputs", {}), f"{where}.inputs")
    for role, ref in inputs.items():
        _str(ref, f"{where}.inputs.{role}")
    return Step(
        id=_str(d["id"], f"{where}.id"),
        transformation=_str(d["transformation"], f"{where}.transformation"),
        inputs=inputs,
        outputs={role: fact_from_dict(f, f"{where}.outputs.{role}")
                 for role, f in _map(d.get("outputs", {}), f"{where}.outputs").items()},
        params=_map(d.get("params", {}), f"{where}.params"),
    )


def proof_from_dict(d: Any) -> Proof:
    d = _obj(d, "proof", {"steps"}, set())
    return Proof(steps=tuple(step_from_dict(s, f"proof.steps[{i}]")
                             for i, s in enumerate(_list(d["steps"], "proof.steps"))))


def fact_to_dict(f: Fact) -> dict[str, Any]:
    d: dict[str, Any] = {"id": f.id, "type": f.type}
    if f.value is not None:
        d["value"] = f.value
    for k in ("unit", "owner", "why_unknown"):
        if getattr(f, k) is not None:
            d[k] = getattr(f, k)
    if f.status != "truth":
        d["status"] = f.status
    if f.attributes:
        d["attributes"] = dict(f.attributes)
    if f.children:
        d["children"] = [fact_to_dict(c) for c in f.children]
    if f.provenance is not None:
        d["provenance"] = {k: v for k, v in asdict(f.provenance).items() if v is not None}
    if f.evidence_needed:
        d["evidence_needed"] = list(f.evidence_needed)
    return d


def requirement_to_dict(r: Requirement) -> dict[str, Any]:
    d: dict[str, Any] = {"id": r.id}
    if r.selector.fact_id is not None:
        d["fact_id"] = r.selector.fact_id
    else:
        d["where"] = dict(r.selector.where)
    d["predicate"] = r.predicate
    if r.args:
        d["args"] = dict(r.args)
    return d


def proof_to_dict(p: Proof) -> dict[str, Any]:
    return {"steps": [{
        "id": s.id, "transformation": s.transformation, "inputs": dict(s.inputs),
        "outputs": {role: fact_to_dict(f) for role, f in s.outputs.items()},
        **({"params": dict(s.params)} if s.params else {}),
    } for s in p.steps]}


def _failure(f: Failure) -> dict[str, Any]:
    return {k: (list(v) if isinstance(v, tuple) else v)
            for k, v in asdict(f).items() if v not in (None, ())}


def _event(e: TraceEvent) -> dict[str, Any]:
    d: dict[str, Any] = {"kind": e.kind, "subject": e.subject, "status": e.status}
    if e.checks:
        d["checks"] = [{"check": c, "passed": ok, **({"detail": det} if det else {})}
                       for c, ok, det in e.checks]
    if e.failures:
        d["failures"] = [_failure(f) for f in e.failures]
    return d


def filter_trace(v: Verdict, mode: TraceFilter) -> tuple[TraceEvent, ...]:
    """``full``: every event. ``failure_trail``: rejected/skipped events only.
    ``success_path``: accepted requirements and the accepted steps they rest on."""
    if mode == "full":
        return v.trace
    if mode == "failure_trail":
        return tuple(e for e in v.trace if e.status != "accepted")
    if mode == "success_path":
        support = set(v.support)
        return tuple(e for e in v.trace if e.status == "accepted" and (
            e.kind == "requirement" or e.subject in support))
    raise ValueError(f"unknown trace filter {mode!r}; use one of {TRACE_FILTERS}")


def verdict_to_dict(v: Verdict, mode: TraceFilter = "full") -> dict[str, Any]:
    return {
        "valid": v.valid,
        "trust_grade": v.trust_grade,
        "failures": [_failure(f) for f in v.failures],
        "soft_steps": list(v.soft_steps),
        "unverified_facts": list(v.unverified_facts),
        "support": list(v.support),
        "trace_filter": mode,
        "trace": [_event(e) for e in filter_trace(v, mode)],
    }


def dumps(obj: Mapping[str, Any]) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, default=str)
