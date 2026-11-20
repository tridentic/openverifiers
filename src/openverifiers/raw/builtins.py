"""Builtin evaluation: exact rational arithmetic with dimensions, comparisons.

Used by the evaluator and, independently, by the checker. Builtins fire only
when every variable they read is bound ("guarded modes"); evaluation of a
ground expression is a pure function. ``None`` means "no result" (dimension
mismatch, division by zero, non-integer exponent...): the builtin fails.

Trusted code.
"""

from __future__ import annotations

from fractions import Fraction

from .terms import Compound, Dims, Num, Subst, Term, Var, make_dims, order_key, substitute

#: Function symbols evaluated inside ``is`` and comparison literals.
ARITH = frozenset({"+", "-", "*", "/", "^", "abs", "min", "max", "sort_args"})
COMPARISONS = frozenset({"=", "!=", "<", "<=", ">", ">="})


def _dims_scale(d: Dims, k: Fraction) -> Dims:
    return make_dims({n: e * k for n, e in d})


def _dims_add(a: Dims, b: Dims) -> Dims:
    out = dict(a)
    for n, e in b:
        out[n] = out.get(n, Fraction(0)) + e
    return make_dims(out)


def _apply(op: str, args: list[Term]) -> Term | None:
    if op == "sort_args":
        (t,) = args
        if not isinstance(t, Compound):
            return None
        return Compound(t.functor, tuple(sorted(t.args, key=order_key)))
    if not all(isinstance(a, Num) for a in args):
        return None
    nums: list[Num] = [a for a in args if isinstance(a, Num)]
    if op == "-" and len(nums) == 1:
        return Num(-nums[0].value, nums[0].dims)
    if op == "abs" and len(nums) == 1:
        return Num(abs(nums[0].value), nums[0].dims)
    if len(nums) != 2:
        return None
    x, y = nums
    if op in ("+", "-", "min", "max"):
        if x.dims != y.dims:
            return None
        if op == "+":
            return Num(x.value + y.value, x.dims)
        if op == "-":
            return Num(x.value - y.value, x.dims)
        return Num((min if op == "min" else max)(x.value, y.value), x.dims)
    if op == "*":
        return Num(x.value * y.value, _dims_add(x.dims, y.dims))
    if op == "/":
        if y.value == 0:
            return None
        return Num(x.value / y.value, _dims_add(x.dims, _dims_scale(y.dims, Fraction(-1))))
    if op == "^":
        if y.dims or y.value.denominator != 1 or (x.value == 0 and y.value < 0):
            return None
        return Num(x.value ** int(y.value), _dims_scale(x.dims, y.value))
    return None


def evaluate(expr: Term, s: Subst) -> Term | None:
    """Evaluate a ground-after-substitution expression; ``None`` if it fails."""
    t = substitute(expr, s)
    return _eval(t)


def _eval(t: Term) -> Term | None:
    if isinstance(t, Var):
        return None
    if not isinstance(t, Compound):
        return t
    args: list[Term] = []
    for a in t.args:
        v = _eval(a)
        if v is None:
            return None
        args.append(v)
    if t.functor in ARITH:
        return _apply(t.functor, args)
    return Compound(t.functor, tuple(args))


def compare(op: str, left: Term, right: Term, s: Subst) -> bool:
    """Evaluate a comparison literal. Ordering needs numbers of equal dimension."""
    a, b = evaluate(left, s), evaluate(right, s)
    if a is None or b is None:
        return False
    if op == "=":
        return a == b
    if op == "!=":
        return a != b
    if not (isinstance(a, Num) and isinstance(b, Num)) or a.dims != b.dims:
        return False
    if op == "<":
        return a.value < b.value
    if op == "<=":
        return a.value <= b.value
    if op == ">":
        return a.value > b.value
    if op == ">=":
        return a.value >= b.value
    return False
