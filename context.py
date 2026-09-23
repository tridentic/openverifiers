"""VerifierContext — the ergonomic entry point; a thin wrapper, not a
parallel system.

While active, every Fact/Quantity/property construction and every controller
solve result executed inside the block is recorded into the context's ledger.
`verify(target)` builds the same Premise the manual path would and delegates
to the existing Specifier.

    with VerifierContext() as ctx:
        with ctx.freeze():
            # ONLY givens and the target Query go here — your invariants.
            ground = ReferenceFrame(name="ground")
            deer = PointObject(name="deer", frame=ground)
            ...
            target = AggregateQuery({...})   # declared HERE, before solving
        # derivation phase: Controller calls only, no new raw inputs.
        t_catch = ...solve_for(...)
        result = ctx.verify()   # no target argument — it was already frozen

The manual `Premise.of_objects`/`Premise.of` + `Specifier` path remains for
advanced/low-level use; `VerifierContext` is the standard entry point.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Optional

from .facts import Fact, DerivationRecord

_CTX: contextvars.ContextVar = contextvars.ContextVar(
    "verifier_context", default=None)


def note(fact_or_object) -> None:
    """Record a constructed Fact/object into the active context, with
    freeze-enforcement: after ctx.freeze() exits, a raw (underived) Fact is a
    violation — only Controller outputs may appear."""
    ctx = _CTX.get()
    if ctx is None:
        return
    if ctx._in_meta:
        return  # descriptive metadata (time-stamps on qualified results):
                # recorded nowhere, guards skipped — decoration, not inputs
    if isinstance(fact_or_object, Fact):
        if ctx._inside_freeze and fact_or_object.derivation is None:
            ctx._frozen_given_ids.add(id(fact_or_object))
        if ctx._frozen_finalized and fact_or_object.derivation is None:
            raise RuntimeError(
                "no new given facts outside ctx.freeze(): after the premise "
                "is frozen only Controller-produced derivations are allowed")
    ctx._ledger.append(fact_or_object)


def note_query(query) -> None:
    """A Query constructed inside ctx.freeze() is a candidate frozen target.
    The OUTERMOST query (constructed last, possibly wrapping sub-queries)
    becomes the target when the freeze block exits."""
    ctx = _CTX.get()
    if ctx is None or not ctx._inside_freeze:
        return
    ctx._freeze_queries.append(query)


# ---------------------------------------------------------------------------
# Inspectable derivation graph
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GraphNode:
    """One ledger entry: an object or a fact, flat and self-describing."""

    idx: int
    kind: str                        # "object" | "fact"
    name: str                        # display name (object name / fact id=value)
    fact: Optional[Fact] = None      # the fact object (facts only)
    given: Optional[bool] = None
    derivation: Optional[DerivationRecord] = None


@dataclass(frozen=True)
class GraphEdge:
    """A derived fact node -> one of the fact nodes it depended on."""

    node_idx: int
    input_idx: int
    via: str                         # controller_name/rule_name


class Graph:
    """Flat node/edge records built from the context ledger, plus a static
    provenance check that REUSES the shared validator (queries.py) — the same
    walk Specifier.verify performs, never reimplemented."""

    def __init__(self, context):
        self._context = context
        self._ledger = context._ledger
        self._materialized = None

    def _given(self, fact: Fact) -> bool:
        """Same 'given' semantics as build_premise — one shared definition."""
        from .queries import is_given
        return is_given(fact, frozen_given_ids=self._context._frozen_given_ids)

    def _materialize(self):
        if self._materialized is not None:
            return self._materialized
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        fact_nodes = []
        for item in self._ledger:
            idx = len(nodes)
            if isinstance(item, Fact):
                nodes.append(GraphNode(
                    idx=idx, kind="fact",
                    name=f"{item.id}={_short(item)}",
                    fact=item, given=self._given(item),
                    derivation=item.derivation))
                fact_nodes.append(nodes[-1])
            else:
                nodes.append(GraphNode(
                    idx=idx, kind="object",
                    name=getattr(item, "name", None) or
                    getattr(item, "id", "?")))
        for node in fact_nodes:
            rec = node.derivation
            if rec is None:
                continue
            for input_id in rec.input_fact_ids:
                for other in fact_nodes:
                    if other is node or other.fact is None:
                        continue
                    if other.fact.id == input_id:
                        edges.append(GraphEdge(
                            node_idx=node.idx, input_idx=other.idx,
                            via=f"{rec.controller_name}/{rec.rule_name}"))
        self._materialized = (nodes, edges)
        return self._materialized

    def check(self) -> tuple[bool, list[str]]:
        """Static verification: every non-given fact node's derivation must
        resolve recursively. Reuses validate_provenance_of."""
        from .queries import validate_provenance_of
        nodes, _edges = self._materialize()

        def find_inputs(fact_id: str):
            return [n.fact for n in nodes
                    if n.fact is not None and n.fact.id == fact_id]

        problems: list[str] = []
        seen: set[int] = set()
        for node in nodes:
            if node.kind != "fact" or node.given or node.fact is None:
                continue
            problem = validate_provenance_of(
                node.fact, find_inputs, seen,
                label=node.name.split("=")[0],
                is_given=self._given)
            if problem:
                problems.append(problem)
        return (not problems), problems

    def render(self) -> list[str]:
        """Plain flat textual export — the inspectable view."""
        nodes, edges = self._materialize()
        out = []
        for n in nodes:
            if n.kind == "fact":
                flag = "given" if n.given else "derived"
                out.append(f"node {n.idx} [fact:{flag}] {n.name}")
            else:
                out.append(f"node {n.idx} [object] {n.name}")
        for e in edges:
            out.append(f"edge {e.node_idx} -{e.via}-> {e.input_idx}")
        return out

    def to_records(self) -> dict:
        nodes, edges = self._materialize()
        return {
            "nodes": [
                {"idx": n.idx, "kind": n.kind, "name": n.name,
                 "given": n.given,
                 "derivation": None if n.derivation is None else {
                     "controller_name": n.derivation.controller_name,
                     "rule_name": n.derivation.rule_name,
                     "input_fact_ids": list(n.derivation.input_fact_ids)}}
                for n in nodes],
            "edges": [{"node_idx": e.node_idx, "input_idx": e.input_idx,
                       "via": e.via} for e in edges],
        }


def _short(fact: Fact) -> str:
    v = getattr(fact, "value", None)
    if v is None:
        return "?"
    s = str(v)
    return s[:24] if hasattr(s, "__len__") else s


# ---------------------------------------------------------------------------
# VerifierContext
# ---------------------------------------------------------------------------
class VerifierContext:
    def __init__(self):
        self._ledger: list = []
        self._inside_freeze = False
        self._frozen_finalized = False
        self._frozen_given_ids: set[int] = set()
        self._frozen_target = None
        self._freeze_queries: list = []
        self._in_meta = False

    def metadata(self):
        """Descriptive-only construction zone: facts built here (time-stamps
        on qualified results, etc.) are recorded nowhere and never trip the
        freeze guard — decoration, not verification inputs."""
        return _MetaZone(self)

    def __enter__(self) -> "VerifierContext":
        self._token = _CTX.set(self)
        return self

    def __exit__(self, *exc) -> bool:
        _CTX.reset(self._token)
        return False

    # -- graph ---------------------------------------------------------------
    @property
    def graph(self) -> Graph:
        return Graph(self)

    def facts(self) -> list:
        return list(self._ledger)

    # -- premise assembly ----------------------------------------------------
    def build_premise(self):
        from .queries import Premise
        objects = [x for x in self._ledger if not isinstance(x, Fact)]
        facts = [x for x in self._ledger if isinstance(x, Fact)]
        object_attr_ids = set()
        for o in objects:
            for field in getattr(type(o), "model_fields", {}):
                v = getattr(o, field, None)
                if isinstance(v, Fact):
                    object_attr_ids.add(id(v))
        given: dict[str, Fact] = {}
        derived: dict[str, Fact] = {}
        seen_derived: set[str] = set()
        for f in facts:
            if id(f) in object_attr_ids:
                continue
            if f.derivation is not None and id(f) not in self._frozen_given_ids:
                if f.id and f.id != "?" and f.id not in seen_derived and \
                        f.id not in given:
                    label = f.id        # prefer the fact's own unique id
                else:
                    label = f"derived#{len(derived)}"
                seen_derived.add(label)
                derived[label] = f
            else:
                label = f.id if f.id != "?" else f"given#{len(given)}"
                while label in given:
                    label = f"given#{len(given)}"
                given[label] = f
        return Premise.of_objects(*objects, given=given, derived=derived)

    # -- freeze ---------------------------------------------------------------
    def freeze(self):
        if self._frozen_finalized or self._frozen_target is not None:
            raise RuntimeError("ctx.freeze() may run once per context")
        return _Freeze(self)

    def _begin_freeze(self) -> None:
        self._inside_freeze = True

    def _end_freeze(self) -> None:
        self._inside_freeze = False
        self._frozen_finalized = True

    def _set_frozen_target(self, target) -> None:
        if self._frozen_target is not None:
            raise RuntimeError(
                "the frozen target was already declared — redefining, "
                "replacing, or extending it after ctx.freeze() is not allowed")
        self._frozen_target = target

    # -- verify ---------------------------------------------------------------
    def verify(self, target=None):
        """DELEGATES to the existing Specifier/verify machinery — no
        verification logic lives here. Post-freeze, no target argument: the
        frozen target is evaluated against derivations done since."""
        from .queries import Specifier
        if self._frozen_target is not None:
            if target is not None:
                raise RuntimeError(
                    "the target was already frozen inside ctx.freeze() — "
                    "ctx.verify() takes no target argument after freezing")
            target = self._frozen_target
        elif target is None:
            raise RuntimeError(
                "no frozen premise/target — use `with ctx.freeze():` to "
                "declare givens and the target FIRST, then verify()")
        return Specifier(self.build_premise(), target).verify()


class _MetaZone:
    def __init__(self, ctx: "VerifierContext"):
        self._ctx = ctx

    def __enter__(self):
        self._ctx._in_meta = True
        return self

    def __exit__(self, *exc) -> bool:
        self._ctx._in_meta = False
        return False


class _Freeze:
    """The trusted zone: givens + one target Query, declared before any
    derivation. Facts constructed inside are auto-givens; nothing here is
    derived."""

    def __init__(self, ctx: VerifierContext):
        self._ctx = ctx

    def __enter__(self):
        self._ctx._begin_freeze()
        return self

    def __exit__(self, *exc) -> bool:
        if not self._ctx._freeze_queries:
            raise RuntimeError(
                "ctx.freeze() must declare a target Query (e.g. "
                "`target = AggregateQuery({...})`) before exiting the block")
        self._ctx._set_frozen_target(self._ctx._freeze_queries[-1])
        self._ctx._end_freeze()
        return False

    def declare(self, target) -> None:
        """Explicitly declare the target Query inside the freeze block."""
        self._ctx._freeze_queries.append(target)