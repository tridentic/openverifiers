"""Task E — hardened transformation calls and self-describing results."""

import pytest

from openverifiers import (Quantity, Vector3, ThresholdQuery, equality_solve,
                           RoleMismatchError, FrameMismatchError)
from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared, Second)
from openverifiers.domains.physics import (ReferenceFrame, PointObject,
                                           Position, Velocity, Acceleration,
                                           Time, VUAT, SUT, CONST_V_POS)

GROUND = ReferenceFrame(name="ground")
SKY = ReferenceFrame(name="sky")


def _chase_objects():
    deer = PointObject(name="deer", frame=GROUND)
    tiger = PointObject(name="tiger", frame=GROUND)
    with deer.relative_to(GROUND):
        deer.position = Position(value=Vector3.x_only(100.0, Meter()),
                                 unit=Meter())
        deer.velocity = Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                                 unit=MeterPerSecond())
    with tiger.relative_to(GROUND):
        tiger.acceleration = Acceleration(
            value=Vector3.x_only(1.0, MeterPerSecondSquared()),
            unit=MeterPerSecondSquared())
    return deer, tiger


def test_equality_solve_rejects_cross_frame_composition():
    """Required fixture: mismatched frames ACROSS a_inputs/b_inputs must fail
    with the frame-mismatch reason, exactly as a direct solve_for would."""
    deer, tiger = _chase_objects()
    t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
    # deer's position lives in GROUND, but a sky-bound initial-position fact
    # is passed on the B side
    sky_pos = Position(value=Vector3.x_only(0.0, Meter()), unit=Meter(),
                       frame=SKY)
    with pytest.raises(FrameMismatchError) as err:
        equality_solve(
            CONST_V_POS, VUAT, "t",
            a_inputs={"s0": deer.position, "v": deer.velocity},
            b_inputs={"u": t0, "a": tiger.acceleration,
                      "v": sky_pos}, axis=0)
    assert "frame mismatch" in str(err.value)
    assert "ground" in str(err.value) and "sky" in str(err.value)


def test_role_typed_slot_rejects_wrong_role_before_dimensions():
    """A role-typed slot must reject a DIFFERENT role-typed fact up front —
    role-typing, not just dimension-matching."""
    wrong = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                         unit=MeterPerSecondSquared(), frame=GROUND)
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    with pytest.raises(RoleMismatchError) as err:
        VUAT.solve_for("v", u=wrong, a=a, t=t, axis=0)
    assert "role mismatch for slot 'u'" in str(err.value)
    assert "expected Velocity" in str(err.value)
    assert "got Acceleration" in str(err.value)


def test_plain_quantity_still_allowed_as_weak_standin():
    """Bare Quantities (the legacy scalar flows) keep working: role typing
    rejects wrong ROLE-TYPED facts, not untyped stand-ins."""
    u = Quantity(value=0.0, unit=MeterPerSecond())
    a = Quantity(value=2.0, unit=MeterPerSecondSquared())
    t = Quantity(value=3.0, unit=Second())
    v = VUAT.solve_for("v", u=u, a=a, t=t)
    assert v.value == pytest.approx(6.0)


def test_displacement_fact_is_a_qualified_result():
    """'How far the deer moved' is a DisplacementFact — framed, owned,
    time-spanned — not a bare Quantity; its inner quantity is queryable."""
    from openverifiers.domains.physics import DisplacementFact
    deer, tiger = _chase_objects()
    t0_q = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
    t_catch = equality_solve(CONST_V_POS, SUT, "t",
                             a_inputs={"s0": deer.position,
                                       "v": deer.velocity},
                             b_inputs={"u": t0_q, "a": tiger.acceleration},
                             axis=0)
    raw = CONST_V_POS.solve_for("s", s0=deer.position,
                                v=deer.velocity, t=t_catch, axis=0)
    deer_at = DisplacementFact(
        quantity=raw, frame=GROUND, object=deer,
        time_start=Time(value=0.0, unit=Second()),
        time_end=Time(value=t_catch.value, unit=Second()))
    assert isinstance(deer_at, DisplacementFact)
    assert deer_at.frame == GROUND
    assert deer_at.object.name == "deer"
    assert deer_at.quantity.value == pytest.approx(200.0)
    assert deer_at.time_start.value == 0.0
    assert deer_at.time_end.value == pytest.approx(20.0)
    # queries reference the inner quantity directly
    assert ThresholdQuery(deer_at.quantity, min=400.0).description