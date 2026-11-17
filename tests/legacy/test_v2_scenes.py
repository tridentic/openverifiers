"""Typed scene tests on the v2 primitive grammar: scenario-local objects,
typed ownership, and scene independence through primitive compositions.

Covers the structural defects that the bespoke catch-time grammar carried:
no scenario objects inside any grammar module, ownership is a typed
reference, two scenes never share identity or state.
"""

import pytest

from openverifiers.legacy import Quantity, Vector3, FactQuery
from openverifiers.legacy.domains.physics import (Position, Velocity, Acceleration,
                                           PointObject)
from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared)
from openverifiers.legacy.domains.algebra import ALGEBRA
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES
from openverifiers.legacy.scenes import Scene
from openverifiers.legacy.v2 import Registry, submit, run_trace, parse_dsl


def make_chase_scene(name, *, deer_start_m, deer_speed_mps, tiger_accel_mps2,
                     run_m=300.0, v0=0.0) -> Scene:
    s = Scene(name)
    deer = s.object("deer")
    tiger = s.object("tiger")
    with deer:
        s.add(Position(value=Vector3.x_only(deer_start_m, Meter()),
                       unit=Meter(), frame=s.ground, id="deer.start"))
        s.add(Velocity(value=Vector3.x_only(deer_speed_mps, MeterPerSecond()),
                       unit=MeterPerSecond(), frame=s.ground,
                       id="deer.speed"))
    with tiger:
        s.add(Acceleration(
            value=Vector3.x_only(tiger_accel_mps2, MeterPerSecondSquared()),
            unit=MeterPerSecondSquared(), frame=s.ground, id="tiger.a"))
    s.add(Quantity(value=run_m, unit=Meter(), id="run"))
    s.add(Quantity(value=v0, unit=MeterPerSecond(), id="v0"))
    s.add(Quantity(value=0.0, unit=Meter(), id="zero"))
    s.ground_time(0.0)
    return s


REG = Registry([ALGEBRA, PRIMITIVES])
TRACE = """
sd = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed)
st = kin.suvat_s_ut_athalf(u=v0, a=tiger.a)
catch_time = alg.equate(a=sd, b=st) with variable=t
deer_position = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed, t=catch_time)
"""


# -- (1) scenario objects are per-scenario -------------------------------
def test_two_scenarios_share_no_object_identity():
    a = make_chase_scene("A", deer_start_m=100.0, deer_speed_mps=5.0,
                         tiger_accel_mps2=1.0)
    b = make_chase_scene("B", deer_start_m=200.0, deer_speed_mps=10.0,
                         tiger_accel_mps2=1.0)
    assert a.ground is not b.ground
    assert a.facts()["deer.start"].owner is not b.facts()["deer.start"].owner
    assert a.facts()["deer.start"].frame is a.ground
    assert b.facts()["deer.start"].frame is b.ground
    # no cross-talk: same trace, different scenes -> different numbers
    ra = run_trace(REG, a.to_context(), parse_dsl(TRACE))
    rb = run_trace(REG, b.to_context(), parse_dsl(TRACE))
    assert abs(ra.env["catch_time"].value - 20.0) < 1e-9
    assert abs(rb.env["catch_time"].value - (10 + 500 ** 0.5)) < 1e-6


def test_primitive_registry_has_no_scenario_bindings():
    names = set(REG.transforms)
    assert not any(n.startswith("physics_trace") for n in names)
    import inspect as _i
    from openverifiers.legacy.domains import physics_primitives as pp
    assert "GROUND" not in dir(pp)
    assert "DEER" not in dir(pp)


# -- (2) ownership is a typed reference ------------------------------------
def test_owner_is_typed_pointobject_reference():
    s = make_chase_scene("T", deer_start_m=100.0, deer_speed_mps=5.0,
                         tiger_accel_mps2=1.0)
    ds = s.facts()["deer.start"]
    assert isinstance(ds.owner, PointObject)
    assert ds.owner is s.objects[0]
    assert ds.owner.name == "T.deer"


def test_with_owner_block_scopes_multiple_declarations():
    s = Scene("W")
    deer = s.object("deer")
    with deer:
        p = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter(),
                     frame=s.ground, id="p")
        v = Velocity(value=Vector3.x_only(2.0, MeterPerSecond()),
                     unit=MeterPerSecond(), frame=s.ground, id="v")
    assert p.owner is deer and v.owner is deer


def test_owner_frame_mismatch_blocked_at_construction():
    s = Scene("M")
    deer = s.object("deer")
    other = Scene("O")
    with pytest.raises(Exception, match="bound to frame"):
        Position(value=Vector3.x_only(1.0, Meter()), unit=Meter(),
                 frame=other.ground, owner=deer)


def test_background_shape_still_submit_compatible_dict():
    s = make_chase_scene("S", deer_start_m=100.0, deer_speed_mps=5.0,
                         tiger_accel_mps2=1.0)
    bg = s.to_context()
    assert isinstance(bg, dict)
    assert set(bg) >= {"deer.start", "deer.speed", "tiger.a", "run", "v0",
                       "ground.time"}
    res = submit(FactQuery("catch_time", 20.0), traces=TRACE,
                 grammars=[ALGEBRA, PRIMITIVES], background=bg)
    assert res["verdict"] == "pass"


def test_scene_rejects_label_id_divergence():
    s = Scene("D")
    deer = s.object("deer")
    with deer:
        p = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter(),
                     frame=s.ground, id="p")
    with pytest.raises(ValueError, match="diverges"):
        s.add(p, label="other.name")