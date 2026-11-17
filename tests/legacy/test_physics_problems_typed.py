from openverifiers.legacy import (DimensionMismatchError, EquationController, OwnerMismatchError, Quantity, SolveError)

from openverifiers.legacy.domains.physics import (PointObject)
from openverifiers.legacy.domains.units_si import (Meter, Second)
"""Task 1 — the 20 legacy physics problem intents, now via
`EquationController.solve_for` calls (one equation registration per family,
no per-direction rules). Plus the two deliberate failures (owner mismatch,
unit mismatch) and the no-search guarantees: a variable outside the declared
equation cannot even be asked for, and is never looked up elsewhere.
"""

import pytest

from openverifiers.legacy.domains.physics import VUAT, V2U2, SUT, SAVG, FMA, KE, WFS
from openverifiers.legacy.facts import Quantity
from openverifiers.legacy.domains.physics import PointObject
from openverifiers.legacy.errors import (DimensionMismatchError, OwnerMismatchError,
                                  SolveError)
from openverifiers.legacy.domains.units_si import (Meter, Second)

CTRLS = {
    "v = u + a*t": VUAT, "v^2 = u^2 + 2 a s": V2U2,
    "s = u t + (1/2) a t^2": SUT, "s = (u + v)/2 * t": SAVG,
    "F = m a": FMA, "KE = (1/2) m v^2": KE, "W = F s": WFS,
}


def _q(value, unit, owner=None):
    return Quantity(value=float(value), unit=unit, owner=owner)


PASS_CASES = [
    # kinematics
    ("kin-01", "v = u + a*t", "v", {"u": (0, "u"), "a": (2, "a"), "t": (5, "t")}, 10.0),
    ("kin-02", "v = u + a*t", "v", {"u": (10, "u"), "a": (2, "a"), "t": (4, "t")}, 18.0),
    ("kin-03", "v = u + a*t", "v", {"u": (0, "u"), "a": (9.8, "a"), "t": (3, "t")}, 29.4),
    ("kin-19", "v = u + a*t", "v", {"u": (0, "u"), "a": (9.8, "a"), "t": (2, "t")}, 19.6),
    ("kin-15", "v = u + a*t", "t", {"u": (2, "u"), "v": (14, "v"), "a": (3, "a")}, 4.0),
    ("kin-04", "s = u t + (1/2) a t^2", "s",
     {"u": (0, "u"), "a": (4, "a"), "t": (5, "t")}, 50.0),
    ("kin-05", "s = u t + (1/2) a t^2", "s",
     {"u": (5, "u"), "a": (2, "a"), "t": (10, "t")}, 150.0),
    ("kin-18", "s = u t + (1/2) a t^2", "s",
     {"u": (0, "u"), "a": (2, "a"), "t": (6, "t")}, 36.0),
    ("kin-06", "v^2 = u^2 + 2 a s", "v",
     {"u": (0, "u"), "a": (1, "a"), "s": (50, "s")}, 10.0),
    ("kin-13", "v^2 = u^2 + 2 a s", "v",
     {"u": (3, "u"), "a": (2, "a"), "s": (4, "s")}, 5.0),
    ("kin-14", "v^2 = u^2 + 2 a s", "v",
     {"u": (0, "u"), "a": (9.8, "a"), "s": (4.9, "s")}, 9.8),
    ("kin-08c", "s = (u + v)/2 * t", "s",
     {"u": (10, "u"), "v": (30, "v"), "t": (5, "t")}, 100.0),
    ("kin-20", "s = (u + v)/2 * t", "s",
     {"u": (40, "u"), "v": (40, "v"), "t": (2, "t")}, 80.0),
    # dynamics (shared-owner rule; unowned facts pass)
    ("dyn-08", "F = m a", "F", {"m": (10, "m"), "a": (5, "a")}, 50.0),
    ("dyn-09", "F = m a", "a", {"F": (20, "F"), "m": (5, "m")}, 4.0),
    ("dyn-10", "F = m a", "a", {"F": (100, "F"), "m": (20, "m")}, 5.0),
    ("dyn-17", "F = m a", "m", {"F": (12, "F"), "a": (3, "a")}, 4.0),
    # energy
    ("en-11", "W = F s", "W", {"F": (10, "F"), "s": (5, "s")}, 50.0),
    ("en-12", "KE = (1/2) m v^2", "K", {"m": (2, "m"), "v": (3, "v")}, 9.0),
    ("en-16", "KE = (1/2) m v^2", "K", {"m": (4, "m"), "v": (5, "v")}, 50.0),
]


def _knowns(ctrl, table):
    return {var: _q(value, ctrl.vars[unit_var])
            for var, (value, unit_var) in table.items()}


@pytest.mark.parametrize("intent_id,eq_name,target,knowns_tbl,expected",
                         PASS_CASES, ids=[c[0] for c in PASS_CASES])
def test_legacy_physics_intents_via_controller(intent_id, eq_name, target,
                                               knowns_tbl, expected):
    ctrl = CTRLS[eq_name]
    result = ctrl.solve_for(target, **_knowns(ctrl, knowns_tbl))
    assert result.id == target
    assert result.value == pytest.approx(expected, rel=1e-6)


def test_owner_mismatch_rejects_with_clear_reason():
    """dyn-owner-mismatch intent: different owners fail on OWNER, not dim."""
    knowns = {
        "F": _q(100, FMA.vars["F"], owner=PointObject(id="object-a")),
        "m": _q(20, FMA.vars["m"], owner=PointObject(id="object-b")),
    }
    with pytest.raises(OwnerMismatchError) as err:
        FMA.solve_for("a", **knowns)
    assert "owner mismatch" in str(err.value)


def test_unit_mismatch_rejects_before_algebra():
    """kin-unit-mismatch intent: acceleration declared with a length unit
    fails on dimension/unit, distinct from an algebra error."""
    with pytest.raises(DimensionMismatchError) as err:
        SUT.solve_for("s", u=_q(3, SUT.vars["u"]),
                      a=_q(2, Meter()), t=_q(4, Second()))
    assert "dimension mismatch" in str(err.value)


def test_no_search_variable_outside_equation_raises():
    with pytest.raises(SolveError) as err:
        KE.solve_for("x", m=_q(2, KE.vars["m"]), v=_q(3, KE.vars["v"]))
    assert "x" in str(err.value) and "not a variable" in str(err.value)


def test_no_search_missing_known_raises_instead_of_searching():
    """If one declared variable has no known value, the controller refuses —
    it never tries another equation or another path."""
    with pytest.raises(SolveError) as err:
        VUAT.solve_for("v", u=_q(0, VUAT.vars["u"]), a=_q(2, VUAT.vars["a"]))
    assert "without known values" in str(err.value)


def test_target_already_known_raises():
    known = _q(10, KE.vars["K"])
    with pytest.raises(SolveError):
        KE.solve_for("K", K=known, m=_q(2, KE.vars["m"]), v=_q(3, KE.vars["v"]))