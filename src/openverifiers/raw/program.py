"""RawOV programs: atoms, literals, rules, facts, domains, world policies.

RawOV is the kernel IR every OV construct lowers to. This module defines its
data model, the static well-formedness rules (``validate``), the world-policy
rewrite of open-world negation (``effective_body``) and the stratification
condition (``strata_violations``). Both the evaluator and the checker use
these definitions, so they cannot disagree about what a program means.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .builtins import COMPARISONS
from .terms import Term, Var, is_ground, variables

#: Origin prefixes, in increasing order of how much they are taken on trust.
ORIGIN_KINDS = ("axiom", "fact", "import", "domain", "assume")


@dataclass(frozen=True, slots=True)
class Atom:
    """``p(t1..tn)``, or the strong negation ``neg p(t1..tn)`` when ``neg``."""

    pred: str
    args: tuple[Term, ...] = ()
    neg: bool = False

    @property
    def key(self) -> str:
        """Predicate key: ``p`` or ``neg p`` (they are separate relations)."""
        return f"neg {self.pred}" if self.neg else self.pred

    def complement(self) -> Atom:
        return Atom(self.pred, self.args, not self.neg)


@dataclass(frozen=True, slots=True)
class Pos:
    atom: Atom


@dataclass(frozen=True, slots=True)
class Naf:
    """``not atom``. Closed world: atom underivable. Open world: complement derived."""

    atom: Atom


@dataclass(frozen=True, slots=True)
class Assign:
    """``X is expr``: bind X to the value of a ground arithmetic expression."""

    var: Var
    expr: Term


@dataclass(frozen=True, slots=True)
class Compare:
    op: str
    left: Term
    right: Term


Literal = Pos | Naf | Assign | Compare


@dataclass(frozen=True, slots=True)
class Span:
    """Where an item came from in OV source (1-based, end exclusive)."""

    file: str
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    head: Atom
    body: tuple[Literal, ...] = ()
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Fact:
    """A ground atom with an origin ``kind:name`` (see ``ORIGIN_KINDS``)."""

    id: str
    atom: Atom
    origin: str
    span: Span | None = None

    @property
    def assumption(self) -> str | None:
        kind, _, name = self.origin.partition(":")
        return name if kind == "assume" else None


@dataclass(frozen=True, slots=True)
class World:
    pred: str
    closed: bool


@dataclass(frozen=True, slots=True)
class Domain:
    """A finite candidate set: facts ``pred(*args, v)`` for each value ``v``.

    ``complete`` is false when the generator was cut off; then nothing that
    relies on the domain being exhaustive may be concluded.
    """

    id: str
    pred: str
    args: tuple[Term, ...]
    values: tuple[Term, ...]
    complete: bool = True
    span: Span | None = None

    def facts(self) -> Iterator[Fact]:
        for i, v in enumerate(self.values):
            yield Fact(f"{self.id}#{i}", Atom(self.pred, (*self.args, v)), f"domain:{self.id}",
                       self.span)


@dataclass(frozen=True, slots=True)
class Program:
    worlds: tuple[World, ...] = ()
    facts: tuple[Fact, ...] = ()
    rules: tuple[Rule, ...] = ()
    domains: tuple[Domain, ...] = ()
    _closed: frozenset[str] = field(default=frozenset(), init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_closed", frozenset(w.pred for w in self.worlds if w.closed))

    def closed(self, pred: str) -> bool:
        """World policy of a predicate name. Open is the default."""
        return pred in self._closed

    def all_facts(self) -> Iterator[Fact]:
        yield from self.facts
        for d in self.domains:
            yield from d.facts()

    def assumptions(self) -> frozenset[str]:
        return frozenset(a for f in self.facts if (a := f.assumption) is not None)

    def incomplete_preds(self) -> frozenset[str]:
        return frozenset(d.pred for d in self.domains if not d.complete)


def effective_body(rule: Rule, program: Program) -> tuple[Literal, ...]:
    """Apply world policies: open-world ``not p`` becomes the literal ``neg p``.

    (And open-world ``not neg p`` becomes ``p``.) Only closed-world negation
    stays as ``Naf``; it is the only literal that depends on completeness.
    """
    return tuple(
        Pos(lit.atom.complement())
        if isinstance(lit, Naf) and not program.closed(lit.atom.pred) else lit
        for lit in rule.body
    )


def _atom_vars(a: Atom) -> set[str]:
    return {v for t in a.args for v in variables(t)}


def validate(program: Program) -> list[str]:
    """Static well-formedness errors (empty list = well formed).

    * ids are unique across facts, rules and domains; world policies unique;
    * facts and domain values are ground;
    * rules are *safe* when read left to right: positive literals bind
      variables; ``not``, comparisons and ``is`` expressions only read bound
      variables; ``is`` binds a fresh variable; every head variable is bound.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for item_id in ([f.id for f in program.facts] + [r.id for r in program.rules]
                    + [d.id for d in program.domains]):
        if item_id in seen:
            errors.append(f"duplicate id {item_id!r}")
        seen.add(item_id)
    preds = [w.pred for w in program.worlds]
    for p in sorted({p for p in preds if preds.count(p) > 1}):
        errors.append(f"world policy for {p!r} declared more than once")
    for f in program.facts:
        if not all(is_ground(t) for t in f.atom.args):
            errors.append(f"fact {f.id!r} is not ground")
        if f.origin.partition(":")[0] not in ORIGIN_KINDS or ":" not in f.origin:
            errors.append(f"fact {f.id!r} has bad origin {f.origin!r}")
    for d in program.domains:
        if not all(is_ground(t) for t in (*d.args, *d.values)):
            errors.append(f"domain {d.id!r} is not ground")
    for r in program.rules:
        errors.extend(f"rule {r.id!r}: {e}" for e in _safety(r))
    return errors


def _safety(rule: Rule) -> Iterator[str]:
    bound: set[str] = set()
    for i, lit in enumerate(rule.body, 1):
        if isinstance(lit, Pos):
            bound |= _atom_vars(lit.atom)
            continue
        if isinstance(lit, Naf):
            reads = _atom_vars(lit.atom)
        elif isinstance(lit, Compare):
            if lit.op not in COMPARISONS:
                yield f"literal {i}: unknown comparison {lit.op!r}"
            reads = set(variables(lit.left)) | set(variables(lit.right))
        else:
            reads = set(variables(lit.expr))
            if lit.var.name in bound:
                yield f"literal {i}: {lit.var.name} is already bound (use =)"
        unbound = sorted(reads - bound)
        if unbound:
            yield f"literal {i} reads unbound variable(s) {', '.join(unbound)}"
        if isinstance(lit, Assign):
            bound.add(lit.var.name)
    free = sorted(_atom_vars(rule.head) - bound)
    if free:
        yield f"head variable(s) {', '.join(free)} not bound by the body"


def strata_violations(program: Program, strata: dict[str, int]) -> list[str]:
    """Check a stratum assignment: >= for positive, > for closed-world negation."""
    def s(key: str) -> int:
        return strata.get(key, 0)
    out: list[str] = []
    for r in program.rules:
        h = s(r.head.key)
        for lit in effective_body(r, program):
            if isinstance(lit, Pos) and s(lit.atom.key) > h:
                out.append(f"rule {r.id!r}: {lit.atom.key} is in a higher stratum than its head")
            if isinstance(lit, Naf) and s(lit.atom.key) >= h:
                out.append(f"rule {r.id!r}: 'not {lit.atom.key}' is not in a lower stratum")
    return out
