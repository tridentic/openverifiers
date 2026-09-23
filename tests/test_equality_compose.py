from openverifiers import (EquationController, Quantity, SolveError, equality_solve)

from openverifiers.domains.units_si import (Meter, MeterPerSecond, MeterPerSecondSquared, Second)
"""Task 5 — ad-hoc equations banned; composition is the trusted mechanism."""

import pytest

from openverifiers.domains.physics import SAVG, SUT, CONST_V_POS
from openverifiers.errors import SolveError


def test_ad_hoc_equation_construction_banned_outside_domains():
    import sympy as sp
    t, v = sp.symbols("t v")
    with pytest.raises(RuntimeError, match="ad-hoc equations are banned"):
        EquationController(
            "script: v = 2 t", v - 2 * t,
            vars={"v": MeterPerSecond(), "t": Second()})


def test_equality_solve_composes_two_trusted_relations():
    """Catch time: deer (constant-velocity position, s0=100, v=5) meets the
    tiger (constant-acceleration, u=0, a=1). Composed from two trusted
    relations — no new equation anywhere."""
    s0 = Quantity(value=100.0, unit=Meter(), id="d0")
    v = Quantity(value=5.0, unit=MeterPerSecond(), id="v")
    a = Quantity(value=1.0, unit=MeterPerSecondSquared(), id="a")
    t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")

    t_catch = equality_solve(
        CONST_V_POS, SUT, "t",
        a_inputs={"s0": s0, "v": v},
        b_inputs={"u": t0, "a": a})
    assert t_catch.value == pytest.approx(20.0)

    # deer position at catch, via a trusted solve
    pos = CONST_V_POS.solve_for("s", s0=s0, v=v, t=t_catch)
    assert pos.value == pytest.approx(200.0)


def test_equality_solve_requires_registered_relations():
    # registry check: a name that never registered with any controller
    from openverifiers.controllers import REGISTERED_CONTROLLERS
    class _Fake:
        name = "never-registered"
        vars = {"s": Meter(), "t": Second()}
    with pytest.raises(SolveError, match="REGISTERED"):
        equality_solve(_Fake(), SAVG, "t",
                       a_inputs={}, b_inputs={"u": Quantity(value=1.0,
                                                            unit=MeterPerSecond()),
                                              "v": Quantity(value=1.0,
                                                            unit=MeterPerSecond())})