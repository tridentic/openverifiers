"""OpenVerifiers v2 — trace data schema and the closed DSL parser.

The agent-facing surface is TRACE STEPS ONLY (§P2). A step is plain
Pydantic-validated data; the DSL parser's ONLY valid output is the same step
schema. The parser is a small closed grammar — no eval, no code-interpolation,
no general-purpose language. Assumption scopes (P3) are nested blocks that
flatten to steps carrying their open-scope path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict


class TraceStep(BaseModel):
    """One dispatched action in a trace. References resolve against frozen
    facts (grammar baseline) and any fact this trace has already produced."""

    model_config = ConfigDict(extra="forbid")

    op: str = "transform"               # transform | assume | end
    output_id: str = ""                 # transform: the produced fact's id
    transformation_name: str = ""       # transform: whitelist registry name
    inputs: dict[str, str] = {}         # role -> fact reference (output id)
    params: dict[str, Any] = {}         # closed option payload
    # assumption scope: set by the parser/runner; assume-set by `assume` steps
    scope: tuple[str, ...] = ()
    # assume: the claim under assumption; end: conflict flag for discharge
    claim: str = ""
    conflict: bool = False
    statement: str = ""                 # optional human render text


_STEP_RE = re.compile(
    r"^([A-Za-z_][\w]*)\s*=\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)"  # dotted ns
    r"\s*(?:\(([^)]*)\))?\s*(?:with\s+(.+))?$")
_ASSIGNS_RE = re.compile(r"^assume\s+([A-Za-z_][\w]*)\s*:\s*(.+)$")
_END_RE = re.compile(r"^end(?:\s+contradiction)?$")


def parse_dsl(text: str) -> list[TraceStep]:
    """Parse the closed DSL grammar into TraceStep records.

        out = transform(in1, in2) with k=v
        assume H: claim text
          out2 = transform(in1)          # nested under H
        end                             # conditional discharge
        end contradiction               # reductio discharge

    Returns an ordered step list with scope paths; raises ValueError on
    malformed input. Zero code-execution paths exist in this parser.
    """
    lines = [ln.split("#", 1)[0].strip() for ln in text.splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    lines = [ln for ln in lines if ln]
    steps: list[TraceStep] = []
    scope_stack: list[str] = []
    for ln in lines:
        m = _END_RE.match(ln)
        if m:
            if not scope_stack:
                raise ValueError(f"unbalanced 'end' (no open assumption): {ln!r}")
            steps.append(TraceStep(
                op="end", output_id=scope_stack[-1], scope=tuple(scope_stack),
                conflict=bool("contradiction" in ln)))
            scope_stack.pop()
            continue
        m = _ASSIGNS_RE.match(ln)
        if m:
            assume_id = m.group(1)
            if assume_id in scope_stack:
                raise ValueError(f"assumption {assume_id!r} already open")
            steps.append(TraceStep(
                op="assume", output_id=assume_id, claim=m.group(2).strip(),
                scope=tuple(scope_stack)))
            scope_stack.append(assume_id)
            continue
        m = _STEP_RE.match(ln)
        if not m:
            raise ValueError(f"cannot parse step: {ln!r}")
        out_id, transform, args_s, params_s = m.groups()
        inputs: dict[str, str] = {}
        if args_s:
            for tok in args_s.split(","):
                tok = tok.strip()
                if "=" in tok:
                    role, ref = tok.split("=", 1)
                    inputs[role.strip()] = ref.strip()
                else:
                    inputs[tok] = tok
        params: dict[str, Any] = {}
        if params_s:
            for tok in params_s.split(","):
                k, _, v = tok.strip().partition("=")
                params[k.strip()] = _scalar(v.strip())
        steps.append(TraceStep(
            op="transform", output_id=out_id.strip(),
            transformation_name=transform.strip(), inputs=inputs,
            params=params, scope=tuple(scope_stack)))
    if scope_stack:
        raise ValueError(f"unclosed assumption scope(s): {scope_stack}")
    return steps


def _scalar(tok: str) -> Any:
    if tok in ("true", "True"):
        return True
    if tok in ("false", "False"):
        return False
    if re.match(r"^-?\d+$", tok):
        return int(tok)
    if re.match(r"^-?\d+\.\d*$", tok):
        return float(tok)
    return tok.strip('"')

# --------------------------------------------------------------------------
# P1 — Grammar registry (harness-authored, closed whitelist)
# --------------------------------------------------------------------------

from .facts import (Fact, ActionFact, Quantity, DerivationRecord,
                    ImplicationFact, EnumValue)
from .model import Transformation, ParamTransformation
from .queries import Premise, Specifier, Query, PASS, FAIL


@dataclass(frozen=True)
class Grammar:
    """A named domain bundle: transformation whitelist + trusted baseline.

    Harness-authored only; the runner never derives code from agent text.
    """
    name: str
    transformations: Dict[str, Transformation]
    facts: Dict[str, Fact] = field(default_factory=dict)      # baseline
    exclusive: Tuple[frozenset[str], ...] = ()                 # conflict pairs
    doc: str = ""


class Registry:
    """Closed whitelist across one or more Grammars."""

    def __init__(self, grammars: list[Grammar]):
        self.grammars = {g.name: g for g in grammars}
        self.transforms: dict[str, Transformation] = {}
        self.owner: dict[str, str] = {}
        for g in grammars:
            for local, t in g.transformations.items():
                # single-source naming: the dict key IS the name. A bare key
                # is namespaced by this grammar's own `name`; an explicitly
                # dotted key names itself. Never hand-typed twice.
                qualified = local if "." in local else f"{g.name}.{local}"
                if qualified in self.transforms:
                    raise ValueError(
                        f"duplicate transformation {qualified!r} across "
                        f"grammars {self.owner[qualified]!r} and {g.name!r}")
                t.name = qualified          # the Registry owns the name
                if not callable(getattr(t, "apply", None)):
                    raise TypeError(
                        f"{qualified!r} has no callable apply() — subclass "
                        f"Transformation or pass apply=")
                self.transforms[qualified] = t
                self.owner[qualified] = g.name
        self.facts: Dict[str, Fact] = {}
        for g in grammars:
            self.facts.update(g.facts)

    def lookup(self, name: str) -> Optional[Tuple[Transformation, str]]:
        t = self.transforms.get(name)
        return (t, self.owner[name]) if t else None


# --------------------------------------------------------------------------
# P2/P3 — trace runner: dispatch + scopes + discharge
# --------------------------------------------------------------------------

class TraceStepResult:
    """Per-step outcome with full observability payload."""

    __slots__ = ("index", "step", "status", "reason", "produced", "deps",
                 "qualified")

    def __init__(self, index: int, step, status: str, reason: str = "",
                 produced: Optional[Fact] = None, deps: tuple = (),
                 qualified: Any = None):
        self.index = index
        self.step = step
        self.status = status          # pass | fail | invalid | note
        self.reason = reason
        self.produced = produced
        self.deps = deps
        self.qualified = qualified    # non-Fact wrapper (e.g. DisplacementFact),
                                      # kept for observability only

    def as_dict(self) -> dict:
        return {"index": self.index, "op": self.step.op,
                "id": self.step.output_id,
                "transformation": self.step.transformation_name,
                "status": self.status, "reason": self.reason,
                "deps": list(self.deps),
                "produced_id": None if self.produced is None
                else self.produced.id}


class TraceResult:
    def __init__(self, verdict: str, reason: str, steps: list[TraceStepResult],
                 env: dict[str, Fact], scopes: dict[str, str],
                 registry: "Registry | None" = None):
        self.verdict = verdict        # pass | fail | invalid
        self.reason = reason
        self.steps = steps
        self.env = env
        self.scopes = scopes
        self.registry = registry
        self.produced = [s.produced for s in steps if s.produced is not None]

    def render(self) -> str:
        lines = [f"TRACE VERDICT: {self.verdict} — {self.reason}", ""]
        for s in self.steps:
            indent = "  " * len(s.step.scope)
            mark = {PASS: "[PASS]", FAIL: "[FAIL]", "invalid": "[BAD ]",
                    "note": "[----]"}[s.status]
            if s.step.op == "assume":
                lines.append(f"{indent}assume {s.step.output_id}: "
                             f"{s.step.claim}")
            elif s.step.op == "end":
                word = "contradiction" if s.step.conflict else "discharge"
                lines.append(f"{indent}end ({word}) — {s.reason}")
            else:
                lines.append(f"{indent}{s.step.output_id} = "
                             f"{s.step.transformation_name} "
                             f"{mark} {s.reason}")
                trans = (self.registry.transforms
                         .get(s.step.transformation_name)
                         if self.registry is not None else None)
                if trans is not None and trans.required_inputs():
                    lines.append(f"{indent}    requires: "
                                 f"{', '.join(trans.required_inputs())}")
        return "\n".join(lines)


def _conflicts_with(fact: Fact, env: dict[str, Fact],
                    exclusive: list[frozenset[str]]) -> Optional[Fact]:
    """Return the trusted/env fact contradicting `fact`, else None.

    Conflict = same fact TYPE + action kind + binding (`of`) but a different
    value; a stored negation (kind="negation", of=<id>); or membership of a
    grammar-declared exclusive enum pair (e.g. even/odd) on the same kind.
    """
    for other in env.values():
        if other.id == fact.id:
            continue
        if isinstance(other, ActionFact) and other.kind == "negation":
            if other.value == fact.id or other.of == fact.id:
                return other
        if type(other) is not type(fact):
            continue
        if isinstance(fact, ActionFact) and isinstance(other, ActionFact):
            if fact.kind == other.kind and fact.of == other.of \
                    and fact.value != other.value:
                return other
        if isinstance(fact, Quantity) and isinstance(other, Quantity):
            if fact.unit == other.unit and fact.value != other.value \
                    and fact.status not in ("unknown",) \
                    and other.status not in ("unknown",):
                return other
    if isinstance(fact, ActionFact) and isinstance(fact.value, EnumValue):
        for pair in exclusive:
            if fact.value.value not in pair:
                continue
            for other in env.values():
                if other.id == fact.id or not isinstance(other, ActionFact):
                    continue
                if isinstance(other.value, EnumValue) \
                        and other.kind == fact.kind \
                        and other.value.value in pair \
                        and other.value.value != fact.value.value:
                    return other
    return None


def run_trace(registry: Registry,
              background: Mapping[str, Fact],
              steps: List, *, exclusive: tuple[frozenset[str], ...] = ()) \
        -> TraceResult:
    """Execute `steps` against the closed whitelist. `background` is the
    frozen trusted state (grammar baselines merged by caller).

    Discharge semantics (P3):
      * assume H: ... end                      -> implication H => last product
      * assume H: ... end contradiction        -> reductio: H conflicts with
        trusted/env facts => negation of the conflicting claim
    """
    exclusive = exclusive or ()
    env: Dict[str, Fact] = dict(background)
    scope_claims: dict[str, str] = {}
    scope_products: dict[str, list[Fact]] = {}
    step_results: list[TraceStepResult] = []
    invalid = None

    def payload_kind(p: Fact) -> str:
        return getattr(p, "kind", type(p).__name__)

    for i, step in enumerate(steps):
        if step.op == "assume":
            if step.output_id in scope_claims:
                invalid = f"assumption {step.output_id!r} already open"
                step_results.append(TraceStepResult(
                    i, step, "invalid", invalid))
                break
            if step.output_id not in step.scope:  # parsed scopes may pre-assign
                step = step.model_copy(update={
                    "scope": tuple(list(step.scope) + [step.output_id])})
            scope_claims[step.output_id] = step.claim
            scope_products[step.output_id] = []
            step_results.append(TraceStepResult(
                i, step, "note", f"assumed: {step.claim}"))
            continue
        if step.op == "end":
            if step.output_id not in scope_claims:
                invalid = f"end without open assumption {step.output_id!r}"
                step_results.append(TraceStepResult(i, step, "invalid", invalid))
                break
            products = scope_products.get(step.output_id, [])
            claim = scope_claims.pop(step.output_id)
            del scope_products[step.output_id]
            if step.conflict:
                clash = None
                for p in products:
                    clash = _conflicts_with(p, env, list(exclusive))
                    if clash is not None:
                        break
                if clash is None:
                    reason = (f"contradiction requested but no conflicting "
                              f"fact found for any inference under "
                              f"{step.output_id!r}")
                    step_results.append(TraceStepResult(i, step, "fail", reason))
                    invalid = reason
                    break
                neg = ActionFact(id=f"neg_{clash.id}", kind="negation",
                                 of=clash.id,
                                 value=EnumValue(enum="claim",
                                                 value="not " + clash.id))
                env[f"neg_{clash.id}"] = neg
                step_results.append(TraceStepResult(
                    i, step, "pass",
                    f"reductio: {clash.id} conflicts with trusted state; "
                    f"negation established", neg,
                    tuple(products) + (step.output_id,)))
            else:
                if not products:
                    reason = (f"scope {step.output_id!r} produced no fact "
                              f"to discharge")
                    step_results.append(TraceStepResult(i, step, "fail", reason))
                    invalid = reason
                    break
                last = products[-1]
                impl = ImplicationFact(
                    id=f"imp_{step.output_id}", premise=claim,
                    conclusion=last.id)
                env[f"imp_{step.output_id}"] = impl
                step_results.append(TraceStepResult(
                    i, step, "pass",
                    f"discharged: {claim} => {last.id}", impl,
                    (last.id, step.output_id)))
            continue
        # transform step
        hit = registry.lookup(step.transformation_name)
        if hit is None:
            reason = (f"{step.transformation_name!r} is not in the closed "
                      f"whitelist (no such registered transformation)")
            step_results.append(TraceStepResult(i, step, "invalid", reason))
            invalid = reason
            break
        trans, owner = hit
        inputs: Dict[str, Fact] = {}
        unresolved = []
        for role, ref in step.inputs.items():
            f = env.get(ref)
            if f is None:
                unresolved.append(ref)
                continue
            inputs[role] = f
        if unresolved:
            reason = (f"unresolved input refs: {unresolved}")
            step_results.append(TraceStepResult(i, step, "fail", reason))
            invalid = reason
            break
        missing = [s.name for s in trans.inputs
                   if s.required and s.name not in inputs]
        if missing:
            reason = (f"missing required input(s) {missing} — "
                      f"{step.transformation_name} declares "
                      f"{[s.name for s in trans.inputs if s.required]}")
            step_results.append(TraceStepResult(i, step, "fail", reason))
            invalid = reason
            break
        try:
            if isinstance(trans, ParamTransformation):
                bad = trans.validate_params(step.params)
                if bad:
                    reason = bad
                    step_results.append(TraceStepResult(
                        i, step, "invalid", reason))
                    invalid = reason
                    break
                pre = trans.precond(inputs)
                if pre:
                    step_results.append(TraceStepResult(i, step, "fail", pre))
                    invalid = pre
                    break
                out = trans.apply(inputs, step.params)
            else:
                pre = trans.precond(inputs)
                if pre:
                    step_results.append(TraceStepResult(i, step, "fail", pre))
                    invalid = pre
                    break
                out = trans.apply(inputs)
        except Exception as exc:  # fail closed: never let domain code throw
            reason = f"transformation raised {type(exc).__name__}: {exc}"
            step_results.append(TraceStepResult(i, step, "fail", reason))
            invalid = reason
            break
        # qualified-wrapper tolerance: a transformation may return a
        # non-Fact carrying a `.quantity` Fact (DisplacementFact pattern).
        # The quantity becomes the env/premise fact for queries; the wrapper
        # is preserved on the step result for the qualified observability.
        wrapper = None
        if not isinstance(out, Fact) and hasattr(out, "quantity") \
                and isinstance(getattr(out, "quantity", None), Fact):
            wrapper = out
            out = out.quantity
        out = out.model_copy(update={
            "id": step.output_id,
            "derivation": DerivationRecord(
                controller_name=owner, rule_name=step.transformation_name,
                input_fact_ids=tuple(sorted(f.id for f in
                                            inputs.values()))),
            "dependencies": tuple(step.scope),
        })
        env[step.output_id] = out
        for sid in step.scope:
            if sid in scope_products:
                scope_products[sid].append(out)
        step_results.append(TraceStepResult(
            i, step, PASS, f"{owner}.{step.transformation_name} produced "
            f"{step.output_id}", out,
            tuple(f.id for f in inputs.values()), qualified=wrapper))
    verdict = "pass"
    reason = "trace ran to completion"
    if invalid is not None:
        verdict = "invalid"
        reason = invalid
    return TraceResult(verdict, reason, step_results, env,
                      dict(scope_claims), registry)


# --------------------------------------------------------------------------
# P4/P7 — extraction + external submission entrypoint
# --------------------------------------------------------------------------

from typing import Iterable


def extract_facts(adapter: Callable[[str], list["Fact"]], text: str,
                  *, tier="extracted") -> list[Fact]:
    """Run an extraction adapter (LLM-backed, rule-based, ...) over `text`.

    Every returned fact is stamped provenance="extracted": it is UNVERIFIED
    ground input. nothing in the trace engine trusts it further than any
    other background fact; render keeps the tier visible.
    """
    facts = adapter(text)
    return [f.model_copy(update={"provenance": tier}) for f in facts]


def submit(mission: Query, *, traces: Iterable[str] | str = "",
           grammars: list[Grammar] | None = None,
           background: dict[str, Fact] | None = None,
           registry: Registry | None = None) -> dict:
    """External entrypoint (P7): facts + a mission query + DSL traces.

    Returns a plain-JSON-consumable dict: verdict, per-step results, render,
    and provenance tiers. `grammars`/`background` default to the merged
    standard grammar set when omitted.
    """
    from .domains import standard_grammars
    reg = registry or Registry(grammars or standard_grammars())
    env = dict(reg.facts)
    if background:
        env.update(background)
    if isinstance(traces, str):
        traces = [traces] if traces.strip() else []
    trace_results = []
    for text in traces:
        steps = parse_dsl(text)
        trace_results.append(run_trace(reg, env, steps,
                                       exclusive=sum((g.exclusive for g in
                                                      reg.grammars.values()),
                                                     ())))
        env.update(trace_results[-1].env)
    premise = Premise.of(facts={
        f.id: f for f in env.values()
        if not (isinstance(f, ActionFact) and f.kind == "negation")})
    outcome = Specifier(premise, mission).verify() if mission is not None \
        else None
    parts = [t.render() for t in trace_results]
    tier_counts: dict[str, int] = {}
    for f in env.values():
        k = f.effective_provenance
        tier_counts[k] = tier_counts.get(k, 0) + 1
    # verdict precedence (P1 finding): a failing trace must NEVER be masked
    # by a passable mission — the gate blocks on trace verdict first.
    bad = next((t for t in trace_results if t.verdict != "pass"), None)
    if bad is not None:
        verdict, reason = bad.verdict, bad.reason
    elif outcome is not None:
        verdict, reason = outcome.verdict, outcome.reason
    else:
        verdict, reason = "pass", "all traces ran"
    mission_out = None
    if outcome is not None:
        mission_out = {"verdict": outcome.verdict, "reason": outcome.reason,
                       "subchecks": list(outcome.subchecks)}
    return {
        "verdict": verdict,
        "reason": reason,
        "mission": mission_out,
        "traces": [{"verdict": t.verdict, "reason": t.reason,
                    "steps": [s.as_dict() for s in t.steps]}
                   for t in trace_results],
        "render": "\n\n".join(parts) + (
            f"\n\nMISSION: {outcome.verdict} — {outcome.reason}"
            if outcome else ""),
        "provenance_tiers": tier_counts,
    }
