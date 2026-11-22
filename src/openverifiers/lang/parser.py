"""Parse ``.ov`` text into the AST (Lark, LALR(1))."""

from __future__ import annotations

import re
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken, VisitError

from ..raw.program import Span
from . import ast as A
from .errors import Diagnostic, OVError
from .units import parse_unit, unit_regex

_GRAMMAR = Path(__file__).with_name("grammar.lark")


@cache
def _lark() -> Lark:
    text = _GRAMMAR.read_text(encoding="utf-8").replace("@UNIT@", unit_regex())
    return Lark(text, parser="lalr", propagate_positions=True, maybe_placeholders=True)


class _Fail(Exception):
    def __init__(self, d: Diagnostic) -> None:
        self.d = d


def _number(text: str) -> Fraction:
    return Fraction(text)  # Fraction parses decimals and exponents exactly


@v_args(meta=True)
class _ToAst(Transformer[Token, Any]):
    def __init__(self, file: str, source: str) -> None:
        super().__init__()
        self.file, self.text = file, source

    def sp(self, m: Any) -> Span:
        return Span(self.file, m.line, m.column, m.end_line, m.end_column)

    def tsp(self, t: Token) -> Span:
        return Span(self.file, t.line or 0, t.column or 0, t.end_line or 0, t.end_column or 0)

    # ------------------------------------------------------------ helpers
    def start(self, m: Any, items: list[Any]) -> tuple[Any, ...]:
        return tuple(items)

    def names(self, m: Any, xs: list[Token]) -> tuple[str, ...]:
        return tuple(str(x) for x in xs)

    def dotted(self, m: Any, xs: list[Token]) -> str:
        return ".".join(str(x) for x in xs)

    def args(self, m: Any, xs: list[Any]) -> tuple[Any, ...]:
        return tuple(xs)

    def params(self, m: Any, groups: list[list[A.Param]]) -> tuple[A.Param, ...]:
        return tuple(p for g in groups for p in g)

    def group(self, m: Any, xs: list[Any]) -> list[A.Param]:
        names, ty, default = xs
        return [A.Param(n, str(ty), default, self.sp(m)) for n in names]

    def conj(self, m: Any, xs: list[Any]) -> tuple[Any, ...]:
        return tuple(self._lit(x) for x in xs)

    def _lit(self, x: Any) -> Any:
        if isinstance(x, (A.Cmp, A.Member, A.Not, A.Holds, A.Arrow)):
            return x
        return A.Holds(x, x.span)

    # ------------------------------------------------------------ declarations
    def package(self, m: Any, xs: list[Any]) -> A.Package:
        name, ver = xs
        return A.Package(name, str(ver)[1:] if ver else None, self.sp(m))

    def import_pkg(self, m: Any, xs: list[Any]) -> A.ImportPkg:
        return A.ImportPkg(xs[0], self.sp(m))

    def import_state(self, m: Any, xs: list[Any]) -> A.ImportState:
        return A.ImportState(_unquote(xs[0]), str(xs[1]), self.sp(m))

    def type_decl(self, m: Any, xs: list[Any]) -> A.TypeDecl:
        name, parent, *fields = xs
        fs = tuple(f for f in fields if f is not None)
        return A.TypeDecl(str(name), str(parent) if parent else None, fs, self.sp(m))

    def field(self, m: Any, xs: list[Any]) -> Any:
        if isinstance(xs[0], Token):  # a type field `name: Type`
            return (str(xs[0]), str(xs[1]), self.sp(m))
        obj, name = xs  # postfix field access
        return A.Field(obj, str(name), self.sp(m))

    def predicate(self, m: Any, xs: list[Any]) -> A.PredDecl:
        name, params, out, world = xs
        outputs, functional = out if out else ((), False)
        return A.PredDecl(str(name), params or (), outputs, functional,
                          world == "closed", self.sp(m))

    def out_fn(self, m: Any, xs: list[Token]) -> tuple[tuple[str, ...], bool]:
        return (str(xs[0]),), True

    def out_set(self, m: Any, xs: list[Token]) -> tuple[tuple[str, ...], bool]:
        return tuple(str(x) for x in xs), False

    def world(self, m: Any, xs: list[Token]) -> str:
        return str(xs[0])

    def function(self, m: Any, xs: list[Any]) -> A.FuncDecl:
        name, params, result, unordered = xs
        return A.FuncDecl(str(name), params or (), str(result), unordered is not None,
                          self.sp(m))

    def entity(self, m: Any, xs: list[Any]) -> A.EntityDecl:
        names, ty, value = xs
        return A.EntityDecl(names, str(ty), value, self.sp(m))

    def axiom(self, m: Any, xs: list[Any]) -> A.Axiom:
        kw, name, params, body, head = xs
        if head is None:  # ``axiom name: facts`` has no premises
            body, head = (), body
        return A.Axiom(str(name), params or (), body, head, self.sp(m), basis=str(kw))

    def kind_foundation(self, m: Any, xs: list[Any]) -> str:
        return "foundation"

    def kind_law(self, m: Any, xs: list[Any]) -> str:
        return "law"

    def kind_definition(self, m: Any, xs: list[Any]) -> str:
        return "definition"

    def transformation(self, m: Any, xs: list[Any]) -> A.Axiom:
        name, params, req, ens = xs
        return A.Axiom(str(name), params or (), req, ens, self.sp(m), "transformation")

    def controller(self, m: Any, xs: list[Any]) -> A.Controller:
        name, params, *ctrl = xs
        pipes = tuple(c[1] for c in ctrl if c[0] == "pipe")
        branches = tuple(c[1] for c in ctrl if c[0] == "branch")
        guards = tuple(g for c in ctrl if c[0] == "guard" for g in c[1])
        return A.Controller(str(name), params or (), pipes, branches, guards, self.sp(m))

    def pipe(self, m: Any, xs: list[Token]) -> tuple[str, tuple[str, ...]]:
        return "pipe", tuple(str(x) for x in xs)

    def branch(self, m: Any, xs: list[Token]) -> tuple[str, tuple[str, ...]]:
        return "branch", tuple(str(x) for x in xs)

    def guard(self, m: Any, xs: list[Any]) -> tuple[str, Any]:
        return "guard", xs[0]

    def gen_decl(self, m: Any, xs: list[Any]) -> A.GenDecl:
        name, params, yields, source = xs
        return A.GenDecl(str(name), params or (), str(yields), source, self.sp(m))

    def gen_use(self, m: Any, xs: list[Any]) -> A.GenUse:
        return A.GenUse(xs[0], xs[1], self.sp(m))

    def scenario(self, m: Any, xs: list[Any]) -> A.Scenario:
        name, *rest = xs
        stmts = [x for x in rest if not isinstance(x, (str, type(None)))]
        strs = [x for x in rest if isinstance(x, str)]
        # ``uses`` packages come first (dotted strings); ``extends`` is a Token.
        uses = tuple(x for x in strs if not isinstance(x, Token))
        ext = next((str(x) for x in strs if isinstance(x, Token)), None)
        return A.Scenario(str(name), uses, ext, tuple(stmts), self.sp(m))

    def fact(self, m: Any, xs: list[Any]) -> A.FactStmt:
        lit, *meta = xs
        conf, src = _meta(meta)
        return A.FactStmt(self._lit(lit), conf, src, self.sp(m))

    def assume(self, m: Any, xs: list[Any]) -> A.AssumeStmt:
        name, lit, *meta = xs
        conf, src = _meta(meta)
        return A.AssumeStmt(str(name), self._lit(lit), conf, src, self.sp(m))

    def confidence(self, m: Any, xs: list[Token]) -> tuple[str, Any]:
        return "confidence", _number(str(xs[0]))

    def source(self, m: Any, xs: list[Token]) -> tuple[str, Any]:
        return "source", _unquote(xs[0])

    def tolerance(self, m: Any, xs: list[Token]) -> A.Tolerance:
        return A.Tolerance(_number(str(xs[0])), self.sp(m))

    def test(self, m: Any, xs: list[Any]) -> A.Test:
        return A.Test(str(xs[0]), tuple(xs[1:]), self.sp(m))

    def target(self, m: Any, xs: list[Any]) -> A.Target:
        must = tuple(x[1] for x in xs[1:] if x[0] == "must")
        prefer = tuple(x[1] for x in xs[1:] if x[0] == "prefer")
        return A.Target(str(xs[0]), must, prefer, self.sp(m))

    def must(self, m: Any, xs: list[Any]) -> tuple[str, Any]:
        return "must", xs[0]

    def prefer(self, m: Any, xs: list[Any]) -> tuple[str, Any]:
        return "prefer", xs[0]

    # ------------------------------------------------------------ queries
    def query(self, m: Any, xs: list[Any]) -> A.Query:
        return A.Query(xs[0], _slice(self.text, m, 6), self.sp(m))

    def prove(self, m: Any, xs: list[Any]) -> A.Prove:
        return A.Prove(self._lit(xs[0]), self.sp(m))

    def find(self, m: Any, xs: list[Any]) -> A.Find:
        vs, where, limit = xs
        return A.Find(vs, where or (), self.sp(m), int(str(limit)) if limit else None)

    def unique(self, m: Any, xs: list[Any]) -> A.Unique:
        return A.Unique(xs[0], xs[1] or (), self.sp(m))

    def count(self, m: Any, xs: list[Any]) -> A.Count:
        return A.Count(xs[0], xs[1] or (), self.sp(m))

    def check_is(self, m: Any, xs: list[Any]) -> A.CheckIs:
        return A.CheckIs(xs[0], str(xs[1]), self.sp(m))

    def counterexample(self, m: Any, xs: list[Any]) -> A.Counterexample:
        return A.Counterexample(xs[0], self.sp(m))

    def qvars(self, m: Any, xs: list[A.QVar]) -> tuple[A.QVar, ...]:
        return tuple(xs)

    def qvar_t(self, m: Any, xs: list[Any]) -> A.QVar:
        tok, ty = xs
        return A.QVar(str(tok)[1:], self.tsp(tok), str(ty) if ty else None)

    # ------------------------------------------------------------ object layer
    def fact_type(self, m: Any, xs: list[Any]) -> A.FactType:
        name, *rest = xs
        parents = tuple(str(x) for x in rest if isinstance(x, Token))
        members = tuple(x for x in rest if x is not None and not isinstance(x, Token))
        return A.FactType(str(name), parents, members, self.sp(m))

    def prop(self, m: Any, xs: list[Any]) -> A.Prop:
        return A.Prop(str(xs[0]), xs[1], self.sp(m))

    def invariant(self, m: Any, xs: list[Any]) -> A.Invariant:
        return A.Invariant(str(xs[0]), xs[1], self.sp(m))

    def theorem(self, m: Any, xs: list[Any]) -> A.Invariant:
        return A.Invariant(str(xs[0]), xs[1], self.sp(m), theorem=True, kind="theorem")

    def law(self, m: Any, xs: list[Any]) -> A.Invariant:
        return A.Invariant(str(xs[0]), xs[1], self.sp(m), kind="law")

    def lemma(self, m: Any, xs: list[Any]) -> A.Invariant:
        return A.Invariant(str(xs[0]), xs[1], self.sp(m), theorem=True, kind="lemma")

    def derived(self, m: Any, xs: list[Any]) -> A.Derived:
        return A.Derived(str(xs[0]), xs[1], xs[2], self.sp(m))

    def tyexpr(self, m: Any, xs: list[Any]) -> A.TyExpr:
        name, *args = xs
        return A.TyExpr(str(name), tuple(a for a in args if a is not None), self.sp(m))

    def unit_ty(self, m: Any, xs: list[Any]) -> A.TyExpr:
        return A.TyExpr(str(xs[0]), (), self.sp(m))       # the quotes mark a unit type

    def fseq(self, m: Any, xs: list[Any]) -> tuple[A.Formula, ...]:
        return tuple(xs)

    def fbody(self, m: Any, xs: list[Any]) -> tuple[A.Formula, ...]:
        seq, then = xs
        return seq if then is None else (A.FImp(seq, then, self.sp(m)),)

    def fexists(self, m: Any, xs: list[Any]) -> A.FExists:
        return A.FExists(str(xs[0]), xs[1], xs[2], self.sp(m))

    def fnone(self, m: Any, xs: list[Any]) -> A.FExists:
        return A.FExists(str(xs[0]), xs[1], xs[2], self.sp(m), quant="none")

    def fall_in(self, m: Any, xs: list[Any]) -> A.FExists:
        return A.FExists(str(xs[0]), xs[1], xs[2], self.sp(m), quant="all")

    def fall(self, m: Any, xs: list[Any]) -> A.FAll:
        return A.FAll(str(xs[0]), xs[1], self.sp(m))

    def fnot(self, m: Any, xs: list[Any]) -> A.FNot:
        return A.FNot(xs[0], self.sp(m))

    def fchain(self, m: Any, xs: list[Any]) -> A.FChain:
        return A.FChain(tuple(xs[0::2]), tuple(str(o) for o in xs[1::2]), self.sp(m))

    def whatif(self, m: Any, xs: list[Any]) -> A.WhatIf:
        *changes, then = xs
        return A.WhatIf(tuple(changes), then, self.sp(m))

    def retract(self, m: Any, xs: list[Any]) -> A.Retract:
        return A.Retract(self._lit(xs[0]), self.sp(m))

    def assume_name(self, m: Any, xs: list[Token]) -> A.AssumeName:
        return A.AssumeName(str(xs[0]), self.sp(m))

    def expect(self, m: Any, xs: list[Any]) -> A.Expect:
        verdict, values, *rest = xs
        assuming: tuple[str, ...] | None = None
        if rest and rest[0] is not None:
            assuming = rest[0]
        elif "assuming" in _slice(self.text, m, 0):
            assuming = ()
        return A.Expect(str(verdict), values or (), assuming, self.sp(m))

    # ------------------------------------------------------------ formulas
    def arrow(self, m: Any, xs: list[Any]) -> A.Arrow:
        return A.Arrow(xs[0], xs[1], self.sp(m))

    def not_(self, m: Any, xs: list[Any]) -> A.Not:
        return A.Not(self._lit(xs[0]), self.sp(m))

    def compare(self, m: Any, xs: list[Any]) -> A.Cmp:
        return A.Cmp(str(xs[1]), xs[0], xs[2], self.sp(m))

    def member(self, m: Any, xs: list[Any]) -> A.Member:
        return A.Member(xs[0], xs[1], self.sp(m))

    # ------------------------------------------------------------ expressions
    def _bin(self, op: str, m: Any, xs: list[Any]) -> A.BinOp:
        return A.BinOp(op, xs[0], xs[1], self.sp(m))

    def add(self, m: Any, xs: list[Any]) -> A.BinOp:
        return self._bin("+", m, xs)

    def sub(self, m: Any, xs: list[Any]) -> A.BinOp:
        return self._bin("-", m, xs)

    def mul(self, m: Any, xs: list[Any]) -> A.BinOp:
        return self._bin("*", m, xs)

    def div(self, m: Any, xs: list[Any]) -> A.BinOp:
        return self._bin("/", m, xs)

    def pow(self, m: Any, xs: list[Any]) -> A.BinOp:
        return self._bin("^", m, xs)

    def neg(self, m: Any, xs: list[Any]) -> A.Neg:
        return A.Neg(xs[0], self.sp(m))

    def call(self, m: Any, xs: list[Any]) -> A.Call:
        return A.Call(str(xs[0]), xs[1] or (), self.sp(m))

    def index(self, m: Any, xs: list[Any]) -> A.Index:
        return A.Index(xs[0], xs[1], self.sp(m))

    def tuplelit(self, m: Any, xs: list[Any]) -> A.TupleLit:
        return A.TupleLit(tuple(xs), self.sp(m))

    def pattern(self, m: Any, xs: list[Any]) -> A.Pattern:
        name, *fields = xs
        return A.Pattern(str(name), tuple(f for f in fields if f is not None), self.sp(m))

    def pfield(self, m: Any, xs: list[Any]) -> tuple[str, Any]:
        return str(xs[0]), xs[1]

    def name(self, m: Any, xs: list[Token]) -> A.Name:
        return A.Name(str(xs[0]), self.tsp(xs[0]))

    def qvar(self, m: Any, xs: list[Token]) -> A.QVar:
        return A.QVar(str(xs[0])[1:], self.tsp(xs[0]))

    def string(self, m: Any, xs: list[Token]) -> A.StrLit:
        return A.StrLit(_unquote(xs[0]), self.tsp(xs[0]))

    def unknown(self, m: Any, xs: list[Any]) -> A.UnknownLit:
        return A.UnknownLit(self.sp(m))

    def setlit(self, m: Any, xs: list[Any]) -> A.SetLit:
        return A.SetLit(xs[0] or (), self.sp(m))

    def interval(self, m: Any, xs: list[Any]) -> A.Interval:
        return A.Interval(xs[0], xs[1], self.sp(m))

    def quantity(self, m: Any, xs: list[Token]) -> A.Quantity:
        tok = xs[0]
        text = str(tok)
        num, _, unit = text.replace("\t", " ").partition(" ")
        value = _number(num)
        dims: tuple[tuple[str, Fraction], ...] = ()
        if unit.strip():
            parsed = parse_unit(unit)
            if parsed is None:  # pragma: no cover - the token admits only known units
                raise _Fail(Diagnostic("E103", f"unknown unit '{unit.strip()}'", self.tsp(tok)))
            factor, dims = parsed
            value *= factor
        return A.Quantity(value, dims, text, self.tsp(tok))


def _meta(meta: list[tuple[str, Any]]) -> tuple[Fraction | None, str | None]:
    d = dict(meta)
    return d.get("confidence"), d.get("source")


def _unquote(t: Token | str) -> str:
    s = str(t)[1:-1]
    return s.encode("utf-8").decode("unicode_escape") if "\\" in s else s


def _slice(source: str, m: Any, skip: int) -> str:
    return " ".join(source[m.start_pos:m.end_pos].split())[skip:].strip()


_EXPECTED_NAMES = {"NAME": "a name", "QVAR": "a ?variable", "QUANTITY": "a number",
                   "STRING": "a string", "VERDICT": "a verdict", "CMPOP": "a comparison",
                   "RBRACE": "'}'", "LPAR": "'('", "RPAR": "')'", "COLON": "':'",
                   "COMMA": "','", "LBRACE": "'{'", "_ARROW": "'->'", "WORLD": "open/closed"}


def parse(source: str, file: str = "<input>") -> A.Module:
    """Parse one ``.ov`` file. Raises ``OVError`` with E1xx codes."""
    try:
        tree = _lark().parse(source)
        items = _ToAst(file, source).transform(tree)
    except VisitError as e:
        if isinstance(e.orig_exc, _Fail):
            raise OVError([e.orig_exc.d], {file: source}) from None
        raise
    except UnexpectedInput as e:
        raise OVError([_syntax(e, file, source)], {file: source}) from None
    return A.Module(file, source, items)


def _syntax(e: UnexpectedInput, file: str, source: str) -> Diagnostic:
    line, col = e.line, e.column
    if isinstance(e, UnexpectedCharacters):
        pos = e.pos_in_stream or 0
        ch = source[pos] if pos < len(source) else "end of file"
        return Diagnostic("E102", f"unexpected character {ch!r}", Span(file, line, col, line,
                          col + 1), "remove it, or quote the name with \"...\" if it is text")
    assert isinstance(e, UnexpectedToken)
    tok = e.token
    width = max(1, len(str(tok))) if tok.type != "$END" else 1
    got = "end of file" if tok.type == "$END" else repr(str(tok))
    exp = sorted({_EXPECTED_NAMES.get(t, repr(t.lower()) if t.isupper() else t)
                  for t in e.expected if not t.startswith("__")})
    expected = ", ".join(exp[:6]) + (", ..." if len(exp) > 6 else "")
    before = source.splitlines()[line - 1][:col - 1] if 0 < line <= source.count("\n") + 1 else ""
    if tok.type == "NAME" and re.search(r"\d[ \t]+$", before):
        return Diagnostic("E103", f"unknown unit '{tok}'", Span(file, line, col, line,
                          col + width), "see the units table in docs/LANGUAGE.md; write "
                          f"`2 * {tok}` to multiply by a variable")
    hint = "every statement starts with a keyword (fact, axiom, query, ...)"
    if tok.type == "NAME" and "-" in str(tok):
        hint = "a hyphen inside a name joins it; write `a - b` (with spaces) to subtract"
    elif tok.type == "NAME" and "QUANTITY" in {t for t in e.expected}:
        hint = "unknown unit or missing operator; write `2 * x` to multiply"
    elif tok.type == "QUANTITY":
        hint = "two values in a row; is an operator or comma missing?"
    return Diagnostic("E101", f"unexpected {got}; expected {expected}",
                      Span(file, line, col, line, col + width), hint)
