from openverifiers.legacy import (Quantity, Vector3)

from openverifiers.legacy.domains.physics import (Acceleration, PointObject, Position, ReferenceFrame, Velocity)
from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond, MeterPerSecondSquared, Second)
"""Task 1 — Position/Velocity/Acceleration as genuine 3D vectors."""

import pytest

from openverifiers.legacy.domains.physics import VUAT

GROUND = ReferenceFrame(name="ground")


def test_vector3_arithmetic_and_alignment():
    x_only = Vector3.x_only(10.0, Meter())
    mixed = Vector3(x=1.0, y=2.0, z=3.0, unit=Meter())
    total = x_only + mixed
    assert total.x == 11.0 and total.y == 2.0 and total.z == 3.0
    assert (x_only - x_only).x == 0.0
    assert x_only.is_axis_aligned
    assert not mixed.is_axis_aligned


def test_property_value_is_always_3d():
    vel = Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                   unit=MeterPerSecond(), frame=GROUND)
    assert isinstance(vel.value, Vector3)
    assert vel.value.y == 0.0 and vel.value.z == 0.0


def test_componentwise_solve_checks_all_axes():
    """Object moves only in x: axis-x solves get the real motion; axes y/z
    must be checked as zero, not ignored."""
    v = Velocity(value=Vector3(x=5.0, y=0.0, z=0.0, unit=MeterPerSecond()),
                 unit=MeterPerSecond(), frame=GROUND)
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    vx = VUAT.solve_for("v", u=v, a=a, t=t, axis=0)
    vy = VUAT.solve_for("v", u=v, a=a, t=t, axis=1)
    vz = VUAT.solve_for("v", u=v, a=a, t=t, axis=2)
    assert vx.value == pytest.approx(11.0)
    assert vy.value == pytest.approx(0.0)
    assert vz.value == pytest.approx(0.0)
    assert v.value.y == 0.0 and v.value.z == 0.0


def test_vector_input_without_axis_raises():
    v = Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                 unit=MeterPerSecond(), frame=GROUND)
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    with pytest.raises(ValueError, match="explicit axis"):
        VUAT.solve_for("v", u=v, a=a, t=t)