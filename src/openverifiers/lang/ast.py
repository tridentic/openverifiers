"""The OV abstract syntax tree. Every node carries the span of its source text."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..raw.program import Span

# ---------------------------------------------------------------- expressions


@dataclass(frozen=True)
class Name:
    name: str
    span: Span


@dataclass(frozen=True)
class QVar:
    """``?x``: a variable to solve for in a query (``?p: Point`` gives a type)."""

    name: str
    span: Span
    ty: str | None = None


@dataclass(frozen=True)
class Quantity:
    """An exact number, already converted to base units."""

    value: Fraction
    dims: tuple[tuple[str, Fraction], ...]
    text: str
    span: Span


@dataclass(frozen=True)
class StrLit:
    value: str
    span: Span


@dataclass(frozen=True)
class UnknownLit:
    span: Span


@dataclass(frozen=True)
class Call:
    fn: str
    args: tuple[Expr, ...]
    span: Span


@dataclass(frozen=True)
class Field:
    obj: Expr
    name: str
    span: Span


@dataclass(frozen=True)
class BinOp:
    op: str          # + - * / ^
    left: Expr
    right: Expr
    span: Span


@dataclass(frozen=True)
class Neg:
    arg: Expr
    span: Span


@dataclass(frozen=True)
class SetLit:
    items: tuple[Expr, ...]
    span: Span


@dataclass(frozen=True)
class Interval:
    lo: Expr
    hi: Expr
    span: Span


@dataclass(frozen=True)
class Index:
    """``v[i]`` (indices wrap around: ``v[i+1]`` of the last element is the first)."""

    obj: Expr
    idx: Expr
    span: Span


@dataclass(frozen=True)
class TupleLit:
    items: tuple[Expr, ...]
    span: Span


@dataclass(frozen=True)
class Pattern:
    """``T{field = value, ...}``: a partial instance of a class or record type."""

    cls: str
    fields: tuple[tuple[str, Expr], ...]
    span: Span


Expr = (Name | QVar | Quantity | StrLit | UnknownLit | Call | Field | BinOp | Neg | SetLit
        | Interval | Index | TupleLit | Pattern)

# ---------------------------------------------------------------- literals


@dataclass(frozen=True)
class Holds:
    """A bare expression used as a statement: ``p(x)``."""

    expr: Expr
    span: Span


@dataclass(frozen=True)
class Cmp:
    op: str          # = != < <= > >=
    left: Expr
    right: Expr
    span: Span


@dataclass(frozen=True)
class Member:
    """``x in s``."""

    item: Expr
    coll: Expr
    span: Span


@dataclass(frozen=True)
class Not:
    lit: Holds | Cmp | Member
    span: Span


@dataclass(frozen=True)
class Arrow:
    """``f(x) -> y`` or ``f(x) -> {y, z}`` (facts only)."""

    call: Expr
    out: Expr
    span: Span


Lit = Holds | Cmp | Member | Not
FactLit = Lit | Arrow

# ---------------------------------------------------------------- declarations


@dataclass(frozen=True)
class Param:
    name: str
    type: str
    default: Expr | None
    span: Span


@dataclass(frozen=True)
class Package:
    name: str
    version: str | None
    span: Span


@dataclass(frozen=True)
class ImportPkg:
    name: str
    span: Span


@dataclass(frozen=True)
class ImportState:
    path: str
    alias: str
    span: Span


@dataclass(frozen=True)
class TypeDecl:
    name: str
    parent: str | None
    fields: tuple[tuple[str, str, Span], ...]
    span: Span


@dataclass(frozen=True)
class PredDecl:
    name: str
    params: tuple[Param, ...]
    outputs: tuple[str, ...]   # output types
    functional: bool           # ``-> T`` (one value) vs ``-> {T, ...}`` or none
    closed: bool
    span: Span


@dataclass(frozen=True)
class FuncDecl:
    """A term constructor: ``function c(x: G, y: G) -> G [unordered]``."""

    name: str
    params: tuple[Param, ...]
    result: str
    unordered: bool
    span: Span


@dataclass(frozen=True)
class EntityDecl:
    names: tuple[str, ...]
    type: str
    value: Expr | None
    span: Span


@dataclass(frozen=True)
class Axiom:
    name: str
    params: tuple[Param, ...]
    body: tuple[Lit, ...]
    head: tuple[Lit, ...]
    span: Span
    kind: str = "axiom"   # or "transformation"
    #: for `ov audit`: foundation (`axiom`), law (`law`, empirical) or definition
    basis: str = "foundation"


@dataclass(frozen=True)
class Controller:
    name: str
    params: tuple[Param, ...]
    pipes: tuple[tuple[str, ...], ...]
    branches: tuple[tuple[str, ...], ...]
    guards: tuple[Lit, ...]
    span: Span


@dataclass(frozen=True)
class GenDecl:
    name: str
    params: tuple[Param, ...]
    yields: str
    source: Expr
    span: Span


@dataclass(frozen=True)
class GenUse:
    names: tuple[str, ...]
    source: Expr
    span: Span


@dataclass(frozen=True)
class FactStmt:
    lit: FactLit
    confidence: Fraction | None
    source: str | None
    span: Span


@dataclass(frozen=True)
class AssumeStmt:
    name: str
    lit: FactLit
    confidence: Fraction | None
    source: str | None
    span: Span


@dataclass(frozen=True)
class Tolerance:
    value: Fraction
    span: Span


# ---------------------------------------------------------------- queries


@dataclass(frozen=True)
class Prove:
    lit: Lit
    span: Span


@dataclass(frozen=True)
class Find:
    vars: tuple[QVar, ...]
    where: tuple[Lit, ...]
    span: Span
    limit: int | None = None


@dataclass(frozen=True)
class Retract:
    lit: FactLit
    span: Span


@dataclass(frozen=True)
class AssumeName:
    name: str
    span: Span


@dataclass(frozen=True)
class WhatIf:
    changes: tuple[Retract | AssumeName, ...]
    then: Okql
    span: Span


@dataclass(frozen=True)
class Unique:
    vars: tuple[QVar, ...]
    where: tuple[Lit, ...]
    span: Span


@dataclass(frozen=True)
class Count:
    vars: tuple[QVar, ...]
    where: tuple[Lit, ...]
    span: Span


@dataclass(frozen=True)
class CheckIs:
    obj: Expr
    cls: str
    span: Span


@dataclass(frozen=True)
class Counterexample:
    theorem: str      # Class.theorem
    span: Span


Okql = Prove | Find | WhatIf | Unique | Count | CheckIs | Counterexample
ObjQuery = Unique | Count | CheckIs | Counterexample


@dataclass(frozen=True)
class Query:
    q: Okql
    text: str
    span: Span


@dataclass(frozen=True)
class Expect:
    verdict: str
    values: tuple[Expr, ...]
    assuming: tuple[str, ...] | None
    span: Span


Stmt = EntityDecl | FactStmt | AssumeStmt | GenUse | Query | Expect | Tolerance


@dataclass(frozen=True)
class Scenario:
    name: str
    uses: tuple[str, ...]
    extends: str | None
    stmts: tuple[Stmt, ...]
    span: Span


@dataclass(frozen=True)
class Test:
    name: str
    stmts: tuple[Scenario | Stmt, ...]
    span: Span


@dataclass(frozen=True)
class Target:
    name: str
    must: tuple[tuple[Lit, ...], ...]
    prefer: tuple[tuple[Lit, ...], ...]
    span: Span


@dataclass(frozen=True)
class TyExpr:
    """``Set<Point>``, ``Real``."""

    name: str
    args: tuple[TyExpr, ...]
    span: Span


@dataclass(frozen=True)
class FChain:
    """``a = b > 0``: comparisons chained left to right (one expr: a bare test)."""

    exprs: tuple[Expr, ...]
    ops: tuple[str, ...]
    span: Span


@dataclass(frozen=True)
class FAll:
    """``all i: chain``: i ranges over the indices of the lists the chain indexes with i."""

    var: str
    body: FChain
    span: Span


@dataclass(frozen=True)
class FNot:
    body: FChain
    span: Span


@dataclass(frozen=True)
class FExists:
    """``exists | none | all v in C: body`` (``none``: no element satisfies it)."""

    var: str
    coll: Expr
    body: tuple[Formula, ...]
    span: Span
    quant: str = "exists"


@dataclass(frozen=True)
class FImp:
    """``P -> Q`` inside a class body."""

    premise: tuple[Formula, ...]
    conclusion: tuple[Formula, ...]
    span: Span


Formula = FChain | FAll | FNot | FExists | FImp


@dataclass(frozen=True)
class Prop:
    name: str
    ty: TyExpr
    span: Span


@dataclass(frozen=True)
class Invariant:
    name: str
    body: tuple[Formula, ...]
    span: Span
    theorem: bool = False
    #: invariant (a definition) | law (empirical) | theorem | lemma (a helper theorem)
    kind: str = "invariant"


@dataclass(frozen=True)
class Derived:
    name: str
    ty: TyExpr
    expr: Expr
    span: Span


@dataclass(frozen=True)
class FactType:
    name: str
    parents: tuple[str, ...]
    members: tuple[Prop | Invariant | Derived, ...]
    span: Span


Item = (FactType | Package | ImportPkg | ImportState | TypeDecl | PredDecl | FuncDecl
        | EntityDecl | Axiom | Controller | GenDecl | Scenario | Test | Target | Query | Expect)


@dataclass(frozen=True)
class Module:
    """One parsed ``.ov`` file."""

    file: str
    source: str
    items: tuple[Item, ...] = field(default=())

    @property
    def package(self) -> Package | None:
        return next((i for i in self.items if isinstance(i, Package)), None)
