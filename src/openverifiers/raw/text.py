"""Canonical RawOV text: printer and a small recursive-descent parser.

``parse(dump(p)) == p`` for every well-formed program (tested). Grammar::

    program  := item*
    item     := 'world' name ('open' | 'closed') '.'
              | 'fact' name ':' atom '@' STRING span? '.'
              | 'rule' name ':' atom (':-' literal (',' literal)*)? span? '.'
              | 'domain' name ':' name '(' terms? ')' '=' '{' terms? '}'
                ('complete' | 'partial') span? '.'
    span     := 'span' '(' STRING ',' INT ',' INT ',' INT ',' INT ')'
    literal  := 'not' atom | VAR 'is' expr | expr CMP expr | atom
    atom     := 'neg'? name ('(' terms? ')')?
    expr     := sum;  sum := prod (('+'|'-') prod)*;  prod := pow (('*'|'/') pow)*
    pow      := unary ('^' pow)?;  unary := '-' unary | primary
    primary  := '(' expr ')' | NUM DIMS? | STRING | VAR | name ('(' terms? ')')?
    name     := LOWER_IDENT | QUOTED
    NUM      := '-'? digits ('/' digits | '.' digits)?    (no spaces inside)
    DIMS     := '{' name '^' NUM (',' name '^' NUM)* '}'  (immediately after NUM)

Arithmetic is printed fully parenthesised, so printing is canonical. ``%``
starts a comment.

Trusted code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from .builtins import COMPARISONS
from .program import (
    Assign,
    Atom,
    Compare,
    Domain,
    Fact,
    Literal,
    Naf,
    Pos,
    Program,
    Rule,
    Span,
    World,
)
from .terms import Compound, Num, Str, Sym, Term, Var, make_dims

KEYWORDS = frozenset({"world", "fact", "rule", "domain", "span", "open", "closed", "complete",
                      "partial", "not", "neg", "is"})
INFIX = ("+", "-", "*", "/", "^")
_NAME = re.compile(r"[a-z][A-Za-z0-9_]*\Z")


class RawSyntaxError(ValueError):
    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(f"{line}:{col}: {message}")
        self.line, self.col = line, col


# --------------------------------------------------------------------------- printing


def dump_name(n: str) -> str:
    if _NAME.match(n) and n not in KEYWORDS:
        return n
    return "'" + n.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _dump_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _dump_frac(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def dump_term(t: Term) -> str:
    if isinstance(t, Var):
        return t.name
    if isinstance(t, Sym):
        return dump_name(t.name)
    if isinstance(t, Str):
        return _dump_str(t.value)
    if isinstance(t, Num):
        dims = ",".join(f"{dump_name(k)}^{_dump_frac(e)}" for k, e in t.dims)
        return _dump_frac(t.value) + ("{" + dims + "}" if dims else "")
    if t.functor in INFIX and len(t.args) == 2:
        return f"({dump_term(t.args[0])} {t.functor} {dump_term(t.args[1])})"
    if t.functor == "-" and len(t.args) == 1:
        return f"(- {dump_term(t.args[0])})"
    return f"{dump_name(t.functor)}({', '.join(dump_term(a) for a in t.args)})"


def dump_atom(a: Atom) -> str:
    core = dump_name(a.pred) + (f"({', '.join(dump_term(t) for t in a.args)})" if a.args else "")
    return ("neg " if a.neg else "") + core


def dump_literal(lit: Literal) -> str:
    if isinstance(lit, Pos):
        return dump_atom(lit.atom)
    if isinstance(lit, Naf):
        return "not " + dump_atom(lit.atom)
    if isinstance(lit, Assign):
        return f"{lit.var.name} is {dump_term(lit.expr)}"
    return f"{dump_term(lit.left)} {lit.op} {dump_term(lit.right)}"


def _dump_span(s: Span | None) -> str:
    if s is None:
        return ""
    return f" span({_dump_str(s.file)}, {s.line}, {s.col}, {s.end_line}, {s.end_col})"


def dump_rule(r: Rule) -> str:
    body = " :- " + ", ".join(dump_literal(b) for b in r.body) if r.body else ""
    return f"rule {dump_name(r.id)}: {dump_atom(r.head)}{body}{_dump_span(r.span)}."


def dump(p: Program) -> str:
    lines = [f"world {dump_name(w.pred)} {'closed' if w.closed else 'open'}." for w in p.worlds]
    lines += [f"fact {dump_name(f.id)}: {dump_atom(f.atom)} @{_dump_str(f.origin)}"
              f"{_dump_span(f.span)}." for f in p.facts]
    lines += [f"domain {dump_name(d.id)}: {dump_name(d.pred)}"
              f"({', '.join(dump_term(a) for a in d.args)}) = "
              f"{{{', '.join(dump_term(v) for v in d.values)}}} "
              f"{'complete' if d.complete else 'partial'}{_dump_span(d.span)}." for d in p.domains]
    lines += [dump_rule(r) for r in p.rules]
    return "\n".join(lines) + ("\n" if lines else "")


# --------------------------------------------------------------------------- lexing

_TOKEN = re.compile(r"""
    (?P<ws>\s+|%[^\n]*)
  | (?P<num>\d+(?:/\d+|\.\d+)?)
  | (?P<var>[A-Z_][A-Za-z0-9_]*)
  | (?P<name>[a-z][A-Za-z0-9_]*)
  | (?P<quoted>'(?:[^'\\]|\\.)*')
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<op>:-|<=|>=|!=|[=<>+\-*/^(),.:{}@])
""", re.X)
_VALUE_END = {"num", "var", "name", "quoted", "str"}


@dataclass(frozen=True, slots=True)
class _Tok:
    kind: str  # num | var | name | quoted | str | op | kw | eof
    text: str
    line: int
    col: int


def _unescape(body: str) -> str:
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), body)


def _lex(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    pos, line, line_start = 0, 1, 0
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        col = pos - line_start + 1
        if not m:
            raise RawSyntaxError(f"unexpected character {src[pos]!r}", line, col)
        kind, text = m.lastgroup or "", m.group()
        if kind == "op" and text == "-" and pos + 1 < len(src) and src[pos + 1].isdigit():
            prev = toks[-1] if toks else None
            if prev is None or not (prev.kind in _VALUE_END or prev.text in (")", "}")):
                m2 = _TOKEN.match(src, pos + 1)
                assert m2 is not None and m2.lastgroup == "num"
                kind, text, m = "num", "-" + m2.group(), m2
        if kind == "name" and text in KEYWORDS:
            kind = "kw"
        if kind != "ws":
            toks.append(_Tok(kind, text, line, col))
        nl = text.count("\n")
        if nl:
            line += nl
            line_start = pos + text.rfind("\n") + 1
        pos = m.end()
    toks.append(_Tok("eof", "", line, pos - line_start + 1))
    return toks


# --------------------------------------------------------------------------- parsing


class _Parser:
    def __init__(self, src: str) -> None:
        self.toks = _lex(src)
        self.i = 0

    @property
    def tok(self) -> _Tok:
        return self.toks[self.i]

    def fail(self, msg: str) -> RawSyntaxError:
        return RawSyntaxError(f"{msg}, found {self.tok.text or 'end of input'!r}",
                              self.tok.line, self.tok.col)

    def at(self, text: str) -> bool:
        return self.tok.text == text and self.tok.kind in ("op", "kw")

    def eat(self, text: str) -> None:
        if not self.at(text):
            raise self.fail(f"expected {text!r}")
        self.i += 1

    def take(self, kind: str) -> str:
        if self.tok.kind != kind:
            raise self.fail(f"expected {kind}")
        t = self.tok.text
        self.i += 1
        return t

    def name(self) -> str:
        if self.tok.kind == "name":
            return self.take("name")
        if self.tok.kind == "quoted":
            return _unescape(self.take("quoted")[1:-1])
        raise self.fail("expected a name")

    def string(self) -> str:
        return _unescape(self.take("str")[1:-1])

    def integer(self) -> int:
        t = self.take("num")
        if not re.fullmatch(r"-?\d+", t):
            raise self.fail("expected an integer")
        return int(t)

    # ---- items

    def program(self) -> Program:
        worlds: list[World] = []
        facts: list[Fact] = []
        rules: list[Rule] = []
        domains: list[Domain] = []
        while self.tok.kind != "eof":
            kw = self.tok.text if self.tok.kind == "kw" else ""
            if kw == "world":
                self.i += 1
                pred = self.name()
                if not (self.at("open") or self.at("closed")):
                    raise self.fail("expected 'open' or 'closed'")
                closed = self.tok.text == "closed"
                self.i += 1
                worlds.append(World(pred, closed))
            elif kw == "fact":
                self.i += 1
                fid = self.name()
                self.eat(":")
                atom = self.atom()
                self.eat("@")
                facts.append(Fact(fid, atom, self.string(), self.span()))
            elif kw == "rule":
                self.i += 1
                rid = self.name()
                self.eat(":")
                head = self.atom()
                body: list[Literal] = []
                if self.at(":-"):
                    self.i += 1
                    body.append(self.literal())
                    while self.at(","):
                        self.i += 1
                        body.append(self.literal())
                rules.append(Rule(rid, head, tuple(body), self.span()))
            elif kw == "domain":
                self.i += 1
                did = self.name()
                self.eat(":")
                pred = self.name()
                self.eat("(")
                args = self.terms(")")
                self.eat("=")
                self.eat("{")
                values = self.terms("}")
                if not (self.at("complete") or self.at("partial")):
                    raise self.fail("expected 'complete' or 'partial'")
                complete = self.tok.text == "complete"
                self.i += 1
                domains.append(Domain(did, pred, args, values, complete, self.span()))
            else:
                raise self.fail("expected 'world', 'fact', 'rule' or 'domain'")
            self.eat(".")
        return Program(tuple(worlds), tuple(facts), tuple(rules), tuple(domains))

    def span(self) -> Span | None:
        if not self.at("span"):
            return None
        self.i += 1
        self.eat("(")
        f = self.string()
        nums: list[int] = []
        for _ in range(4):
            self.eat(",")
            nums.append(self.integer())
        self.eat(")")
        return Span(f, *nums)

    def terms(self, close: str) -> tuple[Term, ...]:
        out: list[Term] = []
        if not self.at(close):
            out.append(self.expr())
            while self.at(","):
                self.i += 1
                out.append(self.expr())
        self.eat(close)
        return tuple(out)

    # ---- literals and atoms

    def literal(self) -> Literal:
        if self.at("not"):
            self.i += 1
            return Naf(self.atom())
        if self.at("neg"):
            return Pos(self.atom())
        if self.tok.kind == "var" and self.toks[self.i + 1].text == "is":
            var = Var(self.take("var"))
            self.i += 1
            return Assign(var, self.expr())
        start = self.tok
        left = self.expr()
        if self.tok.kind == "op" and self.tok.text in COMPARISONS:
            op = self.take("op")
            return Compare(op, left, self.expr())
        if isinstance(left, Sym):
            return Pos(Atom(left.name))
        if isinstance(left, Compound) and start.kind in ("name", "quoted"):
            return Pos(Atom(left.functor, left.args))
        raise RawSyntaxError("expected an atom or a comparison", start.line, start.col)

    def atom(self) -> Atom:
        neg = self.at("neg")
        if neg:
            self.i += 1
        pred = self.name()
        args: tuple[Term, ...] = ()
        if self.at("("):
            self.i += 1
            args = self.terms(")")
        return Atom(pred, args, neg)

    # ---- expressions

    def expr(self) -> Term:
        t = self.prod()
        while self.at("+") or self.at("-"):
            op = self.take("op")
            t = Compound(op, (t, self.prod()))
        return t

    def prod(self) -> Term:
        t = self.power()
        while self.at("*") or self.at("/"):
            op = self.take("op")
            t = Compound(op, (t, self.power()))
        return t

    def power(self) -> Term:
        t = self.unary()
        if self.at("^"):
            self.i += 1
            return Compound("^", (t, self.power()))
        return t

    def unary(self) -> Term:
        if self.at("-"):
            self.i += 1
            return Compound("-", (self.unary(),))
        return self.primary()

    def primary(self) -> Term:
        tok = self.tok
        if self.at("("):
            self.i += 1
            t = self.expr()
            self.eat(")")
            return t
        if tok.kind == "num":
            self.i += 1
            value = Fraction(tok.text)
            if self.at("{") and self.tok.col == tok.col + len(tok.text) \
                    and self.tok.line == tok.line:
                self.i += 1
                dims: dict[str, Fraction] = {}
                while True:
                    k = self.name()
                    self.eat("^")
                    dims[k] = Fraction(self.take("num"))
                    if not self.at(","):
                        break
                    self.i += 1
                self.eat("}")
                return Num(value, make_dims(dims))
            return Num(value)
        if tok.kind == "str":
            return Str(self.string())
        if tok.kind == "var":
            return Var(self.take("var"))
        if tok.kind in ("name", "quoted"):
            n = self.name()
            if self.at("("):
                self.i += 1
                return Compound(n, self.terms(")"))
            return Sym(n)
        raise self.fail("expected a term")


def parse(src: str) -> Program:
    """Parse canonical (or hand-written) RawOV text."""
    return _Parser(src).program()


def parse_term(src: str) -> Term:
    p = _Parser(src)
    t = p.expr()
    if p.tok.kind != "eof":
        raise p.fail("trailing input after term")
    return t


def parse_atom(src: str) -> Atom:
    p = _Parser(src)
    a = p.atom()
    if p.tok.kind != "eof":
        raise p.fail("trailing input after atom")
    return a
