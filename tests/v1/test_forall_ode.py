"""D-027: polynomial for-all statements by sums of squares, and verified
closed-form ODE solutions, each in three domains. A theorem's properties are
universally quantified, so a PROVEN theorem at {kernel} is a checked
for-all statement."""

from __future__ import annotations

from pathlib import Path

from openverifiers.runner import run_file

FORALL = """package probe.forall
# mathematics: a^2 + b^2 + c^2 >= ab + bc + ca for all reals (three squares)
fact type Three {
  property a: Real
  property b: Real
  property c: Real
  theorem symmetric: a * a + b * b + c * c >= a * b + b * c + c * a
  theorem quadratic: a * a - 2 * a + 3 >= 2
}
# physics: (m1 + m2)(m1 v1^2 + m2 v2^2) >= (m1 v1 + m2 v2)^2, i.e. the kinetic
# energy is at least that of the centre of mass (a square weighted by m1 m2)
fact type TwoMasses {
  property m1: Mass
  property m2: Mass
  property v1: Velocity
  property v2: Velocity
  invariant positive: m1 > 0 m2 > 0
  theorem centre_of_mass: (m1 + m2) * (m1 * v1 * v1 + m2 * v2 * v2)
                            >= (m1 * v1 + m2 * v2) * (m1 * v1 + m2 * v2)
}
# chemistry: for A + R first order in each, the rate k (a0 - x)(r0 - x) never
# exceeds k ((a0 + r0)/2 - x)^2 (a square weighted by k)
fact type RateBound {
  property k: Real
  property a0: Real
  property r0: Real
  property x: Real
  invariant positive: k > 0
  theorem bound: k * ((a0 + r0) / 2 - x) * ((a0 + r0) / 2 - x) >= k * (a0 - x) * (r0 - x)
}
"""

ODE = """package probe.ode
# physics: RC discharge, q = Q0 exp(-k t) with k = 1/(R C), solves dq/dt = -q/(R C)
fact type Discharge {
  property Q0: Charge
  property R: Resistance
  property C: "A*s/V"
  property k: Frequency
  property t: Time
  invariant positive: R > (0) C > 0
  invariant rate: k * R * C = 1
  theorem solves: R * C * deriv(Q0 * exp(-k * t), t) = -(Q0 * exp(-k * t))
  theorem initial: value_at(Q0 * exp(-k * t), t, 0 s) = Q0
}
# chemistry: first-order kinetics, [A] = A0 exp(-k t) solves d[A]/dt = -k [A]
fact type FirstOrder {
  property A0: Molarity
  property k: Frequency
  property t: Time
  theorem solves: deriv(A0 * exp(-k * t), t) = -k * (A0 * exp(-k * t))
  theorem initial: value_at(A0 * exp(-k * t), t, 0 s) = A0
}
# mathematics: y = b + (y0 - b) exp(a x) solves y' = a (y - b), y(0) = y0
fact type Affine {
  property a: Real
  property b: Real
  property y0: Real
  property x: Real
  theorem solves: deriv(b + (y0 - b) * exp(a * x), x) = a * (b + (y0 - b) * exp(a * x) - b)
  theorem initial: value_at(b + (y0 - b) * exp(a * x), x, 0) = y0
  theorem wrong_initial_is_refuted: value_at(b + (y0 - b) * exp(a * x), x, 0) = b
}
"""


def _theorems(tmp_path: Path, text: str) -> dict[str, tuple[str, frozenset[str]]]:
    f = tmp_path / "t.ov"
    f.write_text(text)
    res = run_file(f, files={str(f)})
    return {a.title.removeprefix("theorem "): (a.verdict, a.trust_base)
            for a in res.classes if a.kind == "theorem"}


def test_forall_by_sums_of_squares_in_three_domains(tmp_path: Path) -> None:
    th = _theorems(tmp_path, FORALL)
    for name in ("Three.symmetric", "Three.quadratic", "TwoMasses.centre_of_mass",
                 "RateBound.bound"):
        assert th[name] == ("PROVEN", frozenset({"kernel"})), (name, th[name])


def test_verified_ode_solutions_in_three_domains(tmp_path: Path) -> None:
    th = _theorems(tmp_path, ODE)
    for name in ("Discharge.solves", "Discharge.initial", "FirstOrder.solves",
                 "FirstOrder.initial", "Affine.solves", "Affine.initial"):
        assert th[name] == ("PROVEN", frozenset({"kernel"})), (name, th[name])
    assert th["Affine.wrong_initial_is_refuted"][0] == "REFUTED"
