"""Differential test: the solver-side symbolic layer against the trusted evaluator.

The expander (objects/expand.py, untrusted) turns a class formula into
polynomials over atoms: roots, exp, ln and pi. The evaluator
(raw/formula.py, with raw/interval.py and raw/surd.py, trusted) computes the same
expression exactly or as a rigorous interval. For random expressions and
rational inputs, this evaluates the expander's polynomial with each atom
enclosed by an interval and checks that the two enclosures overlap. A disjoint
pair means the symbolic layer computes something else than the expression
says: a disagreement, which fails CI.

Each case is also classed by the operations its expression uses, and a refusal
is attributed to the side that refused, so the report shows what the trusted
evaluator cannot cover yet.

**Exp chain rule (untrusted cross-check).** The trusted evaluator does not
differentiate through exp, so derivatives of exp bodies have no trusted oracle.
``exp_derivatives`` compares the expander's chain-rule derivative with a
central finite difference of the trusted evaluator's values (step 2^-64,
200-bit intervals: the difference error is far below the 1e-20 tolerance).
This is a numeric cross-check, not a proof; it closes when the trusted normal
form gains exp atoms (CTO decision 5).

**Surd normal form (D-030, trusted against trusted).** ``surd_normal_form``
compares the certificate checker's polynomial normal form (raw/certificate.py,
with sqrt(k) atoms reduced by sqrt(k)^2 = k) with the evaluator on random
polynomial expressions that contain surd constants.

**Positive-sum multipliers (D-030).** ``positive_sums`` builds random multipliers
(constants that may be negative or surds, hypotheses that may not be positive,
optional squares). Every sum the checker accepts must be > 0 at random points
where the hypotheses hold, and every sum it must refuse (a constant <= 0, a
hypothesis that is not `>`/`<`, only squared terms) must be refused.

    python -m openverifiers.bench.differential --cases 5000 --seed 0
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from fractions import Fraction

from ..objects.expand import EXPS, LOGS, ROOTS, Expander, Poly, SNum
from ..raw import certificate as C
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
    if rng.random() < 0.4:                   # pi inside the integrand (D-030)
        body = Compound("*", (Compound("f.pi", ()), body))
    return Compound(rng.choice(["f.integral", "f.deriv"]), (body, _p("x"), _p("x")))


def _poly_in(rng: random.Random, x: Term) -> Term:
    out: Term = Num(Fraction(rng.randint(-3, 3)))
    for k in range(1, rng.randint(1, 3) + 1):
        term: Term = Num(Fraction(rng.randint(-3, 3)))
        for _ in range(k):
            term = Compound("*", (term, x))
        out = Compound("+", (out, Compound("*", (term, _p(rng.choice(("y", "z")))))))
    return out


class FreeVariable(Exception):
    """The solver's value still mentions a variable although every input was a number:
    always wrong, so it counts as a disagreement."""


def _atom(name: str) -> I.Iv:
    if name == "PI":
        return I.pi()
    if name in ROOTS:
        return I.sqrt(_eval_poly(ROOTS[name]))
    if name in EXPS:
        return I.exp(_eval_poly(EXPS[name]))
    if name in LOGS:
        return I.ln(_eval_poly(LOGS[name]))
    raise FreeVariable(name)


def _eval_poly(p: Poly) -> I.Iv:
    out = I.Iv.of(Fraction(0))
    for mono, c in p.terms:
        t = I.Iv.of(c)
        for v, k in mono:
            t = t * _atom(v).power(k)
        out = out + t
    return out


CLASSES = {"f.sqrt": "sqrt", "f.exp": "exp", "f.ln": "ln", "f.pi": "pi",
           "f.integral": "integral", "f.deriv": "deriv", "/": "division", "^": "power"}


def classes(e: Term) -> set[str]:
    """The operation classes an expression uses ('arithmetic' if none of the above)."""
    out: set[str] = set()

    def go(t: Term) -> None:
        if isinstance(t, Compound):
            if t.functor in CLASSES:
                out.add(CLASSES[t.functor])
            for a in t.args:
                go(a)
    go(e)
    return out or {"arithmetic"}


def one(rng: random.Random) -> tuple[str, Term]:
    """('agree' | 'refused:trusted' | 'refused:solver' | 'DISAGREE: ...', expression)."""
    e = expr(rng)
    props = {p: Num(Fraction(rng.randint(-20, 20), rng.randint(1, 6))) for p in PROPS}
    try:
        trusted = _iv(_Eval(props).expr(e))
    except Unsupported:
        return "refused:trusted", e
    try:
        v = Expander(props).value(e)
        if not isinstance(v, SNum):
            return "refused:solver", e
        solver = _eval_poly(v.p)
    except (Unsupported, I.IntervalError):
        return "refused:solver", e
    except FreeVariable as x:
        return f"DISAGREE: {e} at {props}: solver value mentions {x}", e
    if solver.hi < trusted.lo or trusted.hi < solver.lo:
        return f"DISAGREE: {e} at {props}: solver {solver}, trusted {trusted}", e
    return "agree", e


def run(cases: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    counts = {"agree": 0, "refused": 0, "disagree": 0}
    by_class: dict[str, dict[str, int]] = {}
    examples = []
    for _ in range(cases):
        r, e = one(rng)
        kind = "disagree" if r.startswith("DISAGREE") else r.partition(":")[0]
        counts[kind] += 1
        if kind == "disagree":
            examples.append(r)
        for c in classes(e):
            row = by_class.setdefault(c, {"cases": 0, "refused:trusted": 0,
                                          "refused:solver": 0, "disagree": 0})
            row["cases"] += 1
            if kind != "agree":
                row[r if kind == "refused" else "disagree"] += 1
    return {"cases": cases, "seed": seed, "agree": counts["agree"],
            "refused": counts["refused"], "disagree": counts["disagree"],
            "by_class": dict(sorted(by_class.items())), "examples": examples[:5]}


X = _p("x")
H = Fraction(1, 2 ** 64)                    # finite-difference step
EXP_TOLERANCE = Fraction(1, 10 ** 20)       # relative


def _exp_body(rng: random.Random) -> Term:
    """c(x) * exp(u(x) / k) + d(x): polynomials c, d, u in x with y, z coefficients."""
    u = Compound("/", (_poly_in(rng, X), Num(Fraction(rng.choice([8, 16, 32])))))
    term = Compound("*", (_poly_in(rng, X), Compound("f.exp", (u,))))
    if rng.random() < 0.3:                  # nested: exp of an exp body
        term = Compound("f.exp", (Compound("/", (term, Num(Fraction(64)))),))
    return Compound("+", (term, _poly_in(rng, X)))


def one_exp(rng: random.Random) -> str:
    """The expander's d/dx of an exp body against a finite difference of trusted values."""
    body = _exp_body(rng)
    x0 = Fraction(rng.randint(-12, 12), rng.randint(1, 4))
    props = {"x": Num(x0), "y": Num(Fraction(rng.randint(-6, 6), rng.randint(1, 3))),
             "z": Num(Fraction(rng.randint(-6, 6), rng.randint(1, 3)))}
    try:
        v = Expander(props).value(Compound("f.deriv", (body, X, X)))
        if not isinstance(v, SNum):
            return "refused"
        try:
            sym = _eval_poly(v.p)
        except FreeVariable as x:
            return f"DISAGREE: d/dx {body} at {props}: the derivative mentions {x}"
        hi = _iv(_Eval({**props, "x": Num(x0 + H)}).expr(body))
        lo = _iv(_Eval({**props, "x": Num(x0 - H)}).expr(body))
    except (Unsupported, I.IntervalError):
        return "refused"
    fd = (hi - lo) * I.Iv.of(1 / (2 * H))
    scale = 1 + max(abs(sym.lo), abs(sym.hi), abs(fd.lo), abs(fd.hi))
    gap = max(sym.lo - fd.hi, fd.lo - sym.hi, Fraction(0))
    if gap > EXP_TOLERANCE * scale:
        return f"DISAGREE: d/dx {body} at {props}: chain rule {sym}, finite difference {fd}"
    return "agree"


def exp_derivatives(cases: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    counts = {"agree": 0, "refused": 0, "disagree": 0}
    examples = []
    for _ in range(cases):
        r = one_exp(rng)
        if r.startswith("DISAGREE"):
            counts["disagree"] += 1
            examples.append(r)
        else:
            counts[r] += 1
    return {"cases": cases, "seed": seed, **counts, "examples": examples[:5]}


RADICANDS = (2, 3, 5, 6, 7, 10)


def _surd(rng: random.Random) -> Term:
    k = rng.choice(RADICANDS)
    args: list[Term] = [Num(Fraction(k)), Num(Fraction(rng.randint(-5, 5), rng.randint(1, 4)))]
    if rng.random() < 0.5:
        args += [Num(Fraction(1)), Num(Fraction(rng.randint(-5, 5), rng.randint(1, 3)))]
    return Compound("f.surd", tuple(args))


def _surd_expr(rng: random.Random, depth: int = 3) -> Term:
    if depth == 0 or rng.random() < 0.25:
        r = rng.random()
        return _p(rng.choice(PROPS)) if r < 0.4 else _surd(rng) if r < 0.8 else \
            Num(Fraction(rng.randint(-9, 9), rng.randint(1, 4)))
    k = rng.randrange(4)
    a = _surd_expr(rng, depth - 1)
    if k < 3:
        return Compound(("+", "-", "*")[k], (a, _surd_expr(rng, depth - 1)))
    return Compound("^", (a, Num(Fraction(rng.randint(0, 4)))))


def _eval_cert_poly(p: C.Poly, props: dict[str, Num]) -> I.Iv:
    out = I.Iv.of(Fraction(0))
    for mono, c in p.items():
        t = I.Iv.of(c)
        for v, k in mono:
            x = I.sqrt(I.Iv.of(Fraction(v[5:-1]))) if v.startswith("sqrt(") else \
                I.Iv.of(next(n.value for name, n in props.items() if str(_p(name)) == v))
            t = t * x.power(k)
        out = out + t
    return out


def surd_normal_form(cases: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    counts = {"agree": 0, "refused": 0, "disagree": 0}
    examples = []
    for _ in range(cases):
        e = _surd_expr(rng)
        props = {p: Num(Fraction(rng.randint(-20, 20), rng.randint(1, 6))) for p in PROPS}
        try:
            trusted = _iv(_Eval(props).expr(e))
            normal = _eval_cert_poly(C.poly(e), props)
        except (Unsupported, I.IntervalError):
            counts["refused"] += 1
            continue
        if normal.hi < trusted.lo or trusted.hi < normal.lo:
            counts["disagree"] += 1
            examples.append(f"DISAGREE: {e} at {props}: normal form {normal}, "
                            f"evaluator {trusted}")
        else:
            counts["agree"] += 1
    return {"cases": cases, "seed": seed, **counts, "examples": examples[:5]}


def _cmp(op: str, a: Term, b: Term) -> Term:
    return Compound("f.cmp", (Str(op), a, b))


ZERO = Num(Fraction(0))
SUM_HYPS = {"hx": _cmp(">", _p("x"), ZERO), "hy": _cmp("<", _p("y"), ZERO),
            "hz": _cmp("!=", _p("z"), ZERO), "eq": _cmp("=", _p("z"), _p("z"))}


def one_sum(rng: random.Random) -> str:
    terms = []
    for _ in range(rng.randint(1, 3)):
        c = _surd(rng) if rng.random() < 0.5 else Num(Fraction(rng.randint(-3, 5), 2))
        names = tuple(rng.choice(["hx", "hx", "hy", "hy", "hz", "eq"])
                      for _ in range(rng.randint(0, 2)))
        q = _surd_expr(rng, 1) if rng.random() < 0.3 else None
        terms.append((c, names, q))
    goal = _cmp("=", _p("x"), _p("x"))             # M (x - x) = 0: only the signs decide
    accepted = C.check(goal, SUM_HYPS, C.Certificate(sums=(tuple(terms),)))
    try:
        signs = [_iv(_Eval({}).expr(c)) for c, _, _ in terms]
    except (Unsupported, I.IntervalError):
        return "refused"
    should = all(sg.lo > 0 for sg in signs) and all(
        n in ("hx", "hy") for _, ns, _ in terms for n in ns) and any(
        q is None for _, _, q in terms)
    if accepted != should:
        return f"DISAGREE: sum {terms}: checker {accepted}, expected {should}"
    if not accepted:
        return "rejected"
    for _ in range(5):                              # > 0 wherever the hypotheses hold
        props = {"x": Num(Fraction(rng.randint(1, 30), rng.randint(1, 6))),
                 "y": Num(Fraction(-rng.randint(1, 30), rng.randint(1, 6))),
                 "z": Num(Fraction(rng.randint(-9, 9), rng.randint(1, 3)))}
        total = I.Iv.of(Fraction(0))
        for c, ns, q in terms:
            t = _iv(_Eval(props).expr(c))
            for n in ns:
                t = t * (_iv(_Eval(props).expr(_p("x"))) if n == "hx"
                         else I.Iv.of(Fraction(-1)) * _iv(_Eval(props).expr(_p("y"))))
            if q is not None:
                t = t * _iv(_Eval(props).expr(q)).power(2)
            total = total + t
        if total.hi <= 0:
            return f"DISAGREE: accepted sum {terms} is {total} at {props}"
    return "accepted"


def positive_sums(cases: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    counts = {"accepted": 0, "rejected": 0, "refused": 0, "disagree": 0}
    examples = []
    for _ in range(cases):
        r = one_sum(rng)
        if r.startswith("DISAGREE"):
            counts["disagree"] += 1
            examples.append(r)
        else:
            counts[r] += 1
    return {"cases": cases, "seed": seed, **counts, "examples": examples[:5]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openverifiers.bench.differential")
    ap.add_argument("--cases", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = run(a.cases, a.seed)
    out["exp_derivatives"] = exp_derivatives(a.cases // 5, a.seed)
    out["surd_normal_form"] = surd_normal_form(a.cases // 5, a.seed)
    out["positive_sums"] = positive_sums(a.cases // 5, a.seed)
    print(json.dumps(out, indent=2))
    extra = ("exp_derivatives", "surd_normal_form", "positive_sums")
    return 1 if out["disagree"] or any(out[k]["disagree"] for k in extra) else 0  # type: ignore[index]


if __name__ == "__main__":
    sys.exit(main())
