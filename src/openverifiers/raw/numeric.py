"""Checking instances whose values are intervals (numeric mode).

Trusted code, kept apart from raw/formula.py, which has its own size cap.
"""

from __future__ import annotations

from collections.abc import Mapping

from .formula import ClassDef, Unsupported, _Eval, _iv, holds
from .terms import Compound, Str, Term


def failing_numeric(cls: ClassDef, props: Mapping[str, Term]) -> tuple[str, ...]:
    """Like failing, for an instance where some properties hold an interval f.iv(lo, hi)
    meaning "the value this class defines lies here". Each such property must be the
    left side of exactly one invariant `p = E` (its definition), taken in invariant
    order. E may use only exact values and properties defined earlier, and its
    enclosure must lie within p's interval. Every other invariant must be decided
    strictly. Otherwise: Unsupported. A result of () proves each p within its
    interval."""
    if set(props) != set(cls.props):
        raise Unsupported(f"{cls.name} needs properties {', '.join(cls.props)}")
    pending = {k for k, v in props.items() if isinstance(v, Compound) and v.functor == "f.iv"}
    defined: set[str] = set()
    bad = []
    for n, f in cls.invariants:
        lhs = f.args[1] if isinstance(f, Compound) and f.functor == "f.cmp" \
            and f.args[0] == Str("=") else None
        key = lhs.args[0].value if isinstance(lhs, Compound) and lhs.functor == "f.p" \
            and isinstance(lhs.args[0], Str) else None
        free = _props_in(f)
        if any(p in pending and p != key for p in free):
            raise Unsupported(f"{n} uses an interval property before its definition")
        if key in pending and isinstance(f, Compound):
            enclosure = _iv(_Eval(props).expr(f.args[2]))
            if not enclosure.within(_iv(_Eval(props).expr(f.args[1]))):
                bad.append(n)
            pending.discard(key)
            defined.add(key)
        elif not holds(f, props):
            bad.append(n)
    if pending:
        raise Unsupported(f"no definition for {', '.join(sorted(pending))}")
    return tuple(bad)


def _props_in(t: Term) -> set[str]:
    if isinstance(t, Compound):
        if t.functor == "f.p" and isinstance(t.args[0], Str):
            return {t.args[0].value}
        return {p for a in t.args for p in _props_in(a)}
    return set()
