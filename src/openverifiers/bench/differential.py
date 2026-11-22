"""Differential test: the solver-side symbolic layer against the trusted evaluator.

The expander (objects/expand.py, untrusted) turns a class formula into
polynomials over atoms: roots, exp, ln and pi. The evaluator
(raw/formula.py, with raw/interval.py and raw/surd.py, trusted) computes the same
expression exactly or as a rigorous interval. For random expressions and
rational inputs, this evaluates the expander's polynomial with each atom
enclosed by an interval and checks that the two enclosures overlap. A disjoint
pair means the symbolic layer computes something else than the expression
says: a disagreement, which fails CI.

    python -m openverifiers.bench.differential --cases 5000 --seed 0
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from fractions import Fraction

from ..objects.expand import EXPS, LOGS, ROOTS, Expander, Poly, SNum
from ..raw import interval as I
from ..raw.formula import Unsupported, _Eval, _iv
from ..raw.terms import Compound, Num, Str, Term

PROPS = ("x", "y", "z")


def _p(name: str) -> Compound:
    return Compound("f.p", (Str(name),))


def expr(rng: random.Random, depth: int = 3) -> Term:
    """A random expression; arguments of sqrt and ln are positive by construction."""
    if depth == 0 or rng.random() < 0.25:
        return _p(rng.choice(PROPS)) if rng.random() < 0.6 else \
            Num(Fraction(rng.randint(-9, 9), rng.randint(1, 4)))
    k = rng.randrange(11)
    a = expr(rng, depth - 1)
    if k < 3:
        return Compound(("+", "-", "*")[k], (a, expr(rng, depth - 1)))
    if k == 3:
        return Compound("/", (a, Num(Fraction(rng.choice([-3, -2, 2, 3, 5])))))
    if k == 4:
        return Compound("^", (a, Num(Fraction(rng.randint(0, 3)))))
    if k == 5:
        return Compound("-", (a,))
    pos = Compound("+", (Compound("*", (a, a)), Num(Fraction(rng.randint(1, 5)))))
    if k == 6:
        return Compound("f.sqrt", (pos,))
    if k == 7:
        small = Compound("/", (a, Num(Fraction(rng.choice([4, 8, 16])))))
        return Compound("f.exp", (small,))
    if k == 8:
        return Compound("f.ln", (pos,))
    if k == 9:
        return Compound("f.pi", ())
    body = _poly_in(rng, _p("x"))
    return Compound(rng.choice(["f.integral", "f.deriv"]), (body, _p("x"), _p("x")))


def _poly_in(rng: random.Random, x: Term) -> Term:
    out: Term = Num(Fraction(rng.randint(-3, 3)))
    for k in range(1, rng.randint(1, 3) + 1):
        term: Term = Num(Fraction(rng.randint(-3, 3)))
        for _ in range(k):
            term = Compound("*", (term, x))
        out = Compound("+", (out, Compound("*", (term, _p(rng.choice(("y", "z")))))))
    return out


def _atom(name: str) -> I.Iv:
    if name == "PI":
        return I.pi()
    if name in ROOTS:
        return I.sqrt(_eval_poly(ROOTS[name]))
    if name in EXPS:
        return I.exp(_eval_poly(EXPS[name]))
    if name in LOGS:
        return I.ln(_eval_poly(LOGS[name]))
    raise KeyError(name)


def _eval_poly(p: Poly) -> I.Iv:
    out = I.Iv.of(Fraction(0))
    for mono, c in p.terms:
        t = I.Iv.of(c)
        for v, k in mono:
            t = t * _atom(v).power(k)
        out = out + t
    return out


def one(rng: random.Random) -> str:
    """'agree' | 'refused' (either side declines) | 'DISAGREE: ...'."""
    e = expr(rng)
    props = {p: Num(Fraction(rng.randint(-20, 20), rng.randint(1, 6))) for p in PROPS}
    try:
        trusted = _iv(_Eval(props).expr(e))
    except Unsupported:
        return "refused"
    try:
        v = Expander(props).value(e)
        if not isinstance(v, SNum):
            return "refused"
        solver = _eval_poly(v.p)
    except (Unsupported, I.IntervalError):
        return "refused"
    if solver.hi < trusted.lo or trusted.hi < solver.lo:
        return f"DISAGREE: {e} at {props}: solver {solver}, trusted {trusted}"
    return "agree"


def run(cases: int, seed: int) -> dict[str, int | list[str]]:
    rng = random.Random(seed)
    counts = {"agree": 0, "refused": 0, "disagree": 0}
    examples = []
    for _ in range(cases):
        r = one(rng)
        if r.startswith("DISAGREE"):
            counts["disagree"] += 1
            examples.append(r)
        else:
            counts[r] += 1
    return {"cases": cases, "seed": seed, "agree": counts["agree"],
            "refused": counts["refused"], "disagree": counts["disagree"],
            "examples": examples[:5]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openverifiers.bench.differential")
    ap.add_argument("--cases", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = run(a.cases, a.seed)
    print(json.dumps(out, indent=2))
    return 1 if out["disagree"] else 0


if __name__ == "__main__":
    sys.exit(main())
