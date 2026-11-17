"""OpenVerifiers — conservation laws as ConditionController conditions.

Conservation is an equality-of-sums check, not a solve-for-unknown relation,
so it is a CONDITION, not an EquationController (and never folded into one).
Comparisons use the codebase-wide relative tolerance (1e-6), matching every
other numeric comparison in the project.
"""

from __future__ import annotations

from dataclasses import dataclass

from openverifiers.legacy.controllers import ConditionController
from openverifiers.legacy.facts import Quantity
from openverifiers.legacy.units import (to_canonical)
from openverifiers.legacy.domains.units_si import (KilogramMeterPerSecond, Joule)
from openverifiers.legacy.domains.coding import PASS, FAIL, INAPPLICABLE

from openverifiers.legacy.constants import REL_TOL


@dataclass(frozen=True)
class ConservationCheck:
    """A declared conservation claim: sum(before) == sum(after)."""

    seq: int
    law: str                      # "momentum" | "energy"
    before: tuple[Quantity, ...]
    after: tuple[Quantity, ...]


def _close(a: float, b: float, tol: float = REL_TOL) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


def _balance_condition(name: str, expected_dim, noun: str):
    def condition(performed, chk):
        if not isinstance(chk, ConservationCheck) or chk.law != name:
            return None
        members = list(chk.before) + list(chk.after)
        for q in members:
            if q.dimension != expected_dim:
                return (FAIL,
                        f"dimension mismatch: {q.id} has {q.dimension}, "
                        f"{noun} conservation needs {expected_dim}")
        unknown = [q for q in members if q.status == "unknown"]
        if unknown:
            return (INAPPLICABLE,
                    f"member(s) {[q.id for q in unknown]} are unknown — the "
                    f"balance cannot be checked without guessing, inapplicable "
                    f"not fail")
        sb = sum(to_canonical(q.value, q.unit) for q in chk.before)
        sa = sum(to_canonical(q.value, q.unit) for q in chk.after)
        if _close(sb, sa):
            return (PASS, f"{noun} holds: {sb} == {sa}")
        return (FAIL, f"{noun} violated: before {sb} != after {sa} — a term "
                      f"is missing or wrong")
    return condition


def momentum_conservation(performed, chk):
    return _balance_condition(
        "momentum", KilogramMeterPerSecond().dimension, "momentum")(performed, chk)


def energy_conservation(performed, chk):
    return _balance_condition(
        "energy", Joule().dimension, "energy")(performed, chk)


def build_conservation_controller() -> ConditionController:
    return ConditionController("conservation", [
        ("momentum_conservation", momentum_conservation),
        ("energy_conservation", energy_conservation),
    ])