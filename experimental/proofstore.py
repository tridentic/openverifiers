"""OpenVerifiers — proof / precondition tree & query surface.

A persistent, queryable structure over a verification run. Unlike the ephemeral
trace views, this tree retains every fact node, every derivation edge, AND every
structured precondition (Condition) that gated it — so conditions and preconditions
are first-class, SQL/LINQ-queryable citizens.

Query DSL (matches the DX in docs):
    tree.find(1).where(owner=car, value=300, unit='m')          -> nodes
    tree.assert_any(role='carrier').where_unit_eq('m/s')        -> bool + evidence
    tree.nodes_of(owner=car) / tree.preconditions_of(rule)      -> filters

The tree is a caching/querying layer over the acyclic proof store. It cannot
introduce cycles: every edge records a derivation, and the closure walks only
forward from facts to their proven premises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


@dataclass
class ProofNode:
    """One fact in the proof tree."""
    id: str
    kind: str                          # fact_kind
    value: Any
    unit: Optional[str] = None
    dimension: Optional[dict] = None
    owner: Any = None
    status: str = "given"              # given | derived | target | unknown
    derivation: str = ""               # transformation name that produced it
    premises: list = field(default_factory=list)   # [ProofNode, ...]
    conditions: list = field(default_factory=list) # [Condition, ...] that gated derivation


class ProofQuery:
    """A chainable filter over the proof tree (find()...where()...first())."""

    def __init__(self, nodes: Iterator[ProofNode]):
        self._nodes = list(nodes)

    def where(self, **attrs) -> "ProofQuery":
        """Filter by node attribute equality: where(owner=car, unit='m')."""
        out = []
        for n in self._nodes:
            ok = True
            for k, v in attrs.items():
                if getattr(n, k, None) != v:
                    ok = False
                    break
            if ok:
                out.append(n)
        return ProofQuery(iter(out))

    def where_unit_eq(self, unit: str) -> "ProofQuery":
        return ProofQuery(iter([n for n in self._nodes if n.unit == unit]))

    def where_kind(self, kind: str) -> "ProofQuery":
        return ProofQuery(iter([n for n in self._nodes if n.kind == kind]))

    def where_derived(self) -> "ProofQuery":
        return ProofQuery(iter([n for n in self._nodes if n.status == "derived"]))

    def where_unknown(self) -> "ProofQuery":
        return ProofQuery(iter([n for n in self._nodes if n.status == "unknown"]))

    def first(self) -> Optional[ProofNode]:
        return self._nodes[0] if self._nodes else None

    def count(self) -> int:
        return len(self._nodes)

    def all(self) -> list:
        return list(self._nodes)


class ProofTree:
    """The queryable proof + precondition tree of one verification run."""

    def __init__(self, nodes: Optional[list[ProofNode]] = None):
        self._nodes = nodes or []

    def add(self, node: ProofNode) -> None:
        self._nodes.append(node)

    def find(self, n: int = 0) -> ProofQuery:
        """find(n) -> ProofQuery over all nodes (matches ov.find(n).where(...))."""
        return ProofQuery(iter(self._nodes))

    def nodes(self) -> list:
        return list(self._nodes)

    def nodes_of(self, *, owner=None, kind=None, status=None) -> list:
        """SQL/LINQ-like: nodes_of(owner=car)."""
        out = self._nodes
        if owner is not None:
            out = [n for n in out if n.owner == owner]
        if kind is not None:
            out = [n for n in out if n.kind == kind]
        if status is not None:
            out = [n for n in out if n.status == status]
        return out

    def preconditions_of(self, rule: str) -> list:
        """All Conditions that gated the given rule's firings."""
        out = []
        for n in self._nodes:
            if n.derivation == rule:
                out.extend(n.conditions)
        return out

    def conditions_of(self, *, kind=None, role=None) -> list:
        """Query preconditions by kind or role across the whole tree."""
        out = []
        for n in self._nodes:
            for c in n.conditions:
                if kind is not None and c.kind != kind:
                    continue
                if role is not None and role not in c.roles:
                    continue
                out.append(c)
        return out

    def assert_any(self, **attrs) -> tuple[bool, list]:
        """Assert at least one node matches all attributes -> (found, matching)."""
        m = ProofQuery(iter(self._nodes)).where(**attrs).all()
        return bool(m), m

    def to_dict(self) -> dict:
        return {"nodes": [{
            "id": n.id, "kind": n.kind, "value": str(n.value),
            "unit": n.unit, "dimension": n.dimension, "owner": str(n.owner),
            "status": n.status, "derivation": n.derivation,
            "premises": [p.id for p in n.premises],
            "conditions": [c.describe() for c in n.conditions],
        } for n in self._nodes]}


def tree_from_result(engine_facts: dict, trace: list[dict], target_id: str,
                     conditions_map: dict[str, list] | None = None) -> ProofTree:
    """Build a ProofTree from an engine run's fact store + trace.

    engine_facts: {fact_id: Fact} (from Engine._facts).
    trace: full verbositive trace from the run.
    conditions_map: {rule_name: [Condition,...]} to attach to derived nodes.
    """
    tree = ProofTree()
    root_by_id = {}
    for fid, fact in engine_facts.items():
        node = ProofNode(
            id=fid,
            kind=fact.attributes.get("fact_kind", ""),
            value=fact.value,
            unit=fact.attributes.get("unit"),
            dimension=fact.attributes.get("dimension"),
            owner=fact.attributes.get("owner"),
            status="derived" if fact.status == "derived" else ("target" if fact.status == "target" else ("unknown" if fact.status == "unknown" else "given")),
            derivation=fact.derivation or "",
        )
        root_by_id[fid] = node
        tree.add(node)
    # attach premises + conditions from origins
    parents = {}
    for ev in trace:
        if ev.get("type") == "derive":
            parents.setdefault(ev["fact_id"], []).extend(ev.get("inputs", []))
    for fid, node in root_by_id.items():
        for pid in parents.get(fid, []):
            if pid in root_by_id:
                node.premises.append(root_by_id[pid])
        if node.derivation and conditions_map:
            node.conditions = list(conditions_map.get(node.derivation, []))
    return tree