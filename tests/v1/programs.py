"""Shared RawOV programs and a hypothesis strategy for random programs."""

from __future__ import annotations

from pathlib import Path

from hypothesis import strategies as st

from openverifiers.kernel import NotStratifiable, stratify
from openverifiers.raw import (
    Atom,
    Fact,
    Naf,
    Pos,
    Program,
    Rule,
    Sym,
    Var,
    World,
    parse,
)

ROOT = Path(__file__).resolve().parents[2]
Q11 = ROOT / "examples" / "raw" / "q11.rawov"


def q11() -> Program:
    return parse(Q11.read_text())


REACH = parse("""
world reach closed.
fact e1: edge(a, b) @"fact:t".
fact e2: edge(b, c) @"fact:t".
fact e3: edge(c, d) @"assume:h".
fact n1: node(a) @"fact:t".
fact n2: node(d) @"fact:t".
rule r1: reach(X, Y) :- edge(X, Y).
rule r2: reach(X, Z) :- reach(X, Y), edge(Y, Z).
rule r3: unreach(X, Y) :- node(X), node(Y), not reach(X, Y).
""")

PENGUIN = parse("""
world abnormal closed.
fact b1: bird(tweety) @"fact:t".
fact b2: bird(pingu) @"fact:t".
fact p1: penguin(pingu) @"fact:t".
fact w1: wounded(tweety) @"assume:hurt".
rule ab1: abnormal(X) :- penguin(X).
rule ab2: abnormal(X) :- wounded(X).
rule fl: flies(X) :- bird(X), not abnormal(X).
rule nf: neg flies(X) :- penguin(X).
""")

CONSTS = ("a", "b", "c")
PREDS = ("p", "q", "r", "s")
ASSUMPTIONS = ("x", "y")


@st.composite
def programs(draw: st.DrawFn, *, allow_neg: bool = True) -> Program:
    """Small random safe programs (unary/binary predicates over three constants)."""
    arity = {p: draw(st.integers(1, 2)) for p in PREDS}
    const = st.sampled_from(CONSTS).map(Sym)
    facts = []
    for i in range(draw(st.integers(1, 8))):
        p = draw(st.sampled_from(PREDS[:2]))
        neg = allow_neg and draw(st.booleans()) and draw(st.booleans())
        origin = draw(st.sampled_from(["fact:t", "fact:t", "assume:x", "assume:y"]))
        facts.append(Fact(f"f{i}", Atom(p, tuple(draw(const) for _ in range(arity[p])), neg),
                          origin))
    rules = []
    var = st.sampled_from(["X", "Y", "Z"]).map(Var)
    for i in range(draw(st.integers(0, 5))):
        body: list[Pos | Naf] = []
        bound: set[str] = set()
        for _ in range(draw(st.integers(1, 2))):
            p = draw(st.sampled_from(PREDS))
            args = tuple(draw(st.one_of(var, const)) for _ in range(arity[p]))
            bound |= {a.name for a in args if isinstance(a, Var)}
            body.append(Pos(Atom(p, args, allow_neg and draw(st.booleans()) and draw(
                st.booleans()))))
        pool: list[Var | Sym] = [Var(v) for v in sorted(bound)] or [Sym("a")]
        if allow_neg and draw(st.booleans()):
            p = draw(st.sampled_from(PREDS))
            body.append(Naf(Atom(p, tuple(draw(st.sampled_from([*pool, Sym("a")]))
                                          for _ in range(arity[p])))))
        h = draw(st.sampled_from(PREDS[1:]))
        head = Atom(h, tuple(draw(st.sampled_from(pool)) for _ in range(arity[h])),
                    allow_neg and draw(st.booleans()) and draw(st.booleans()))
        rules.append(Rule(f"r{i}", head, tuple(body)))
    worlds = tuple(World(p, True) for p in PREDS if draw(st.booleans()))
    prog = Program(worlds, tuple(facts), tuple(rules))
    try:
        stratify(prog)
    except NotStratifiable:
        from hypothesis import assume
        assume(False)
    return prog

NAT_SRC = """
fact z: nat(zero) @"fact:t".
rule s: nat(s(X)) :- nat(X).
"""
