"""Pursuit problem (SSC-style) solved with ONLY syllabus primitives.

No scenario class, no pre-composed transformation: the trace binds each
registered relation with the frozen facts, and the generic alg.equate
step closes the two position expressions on the shared unknown t — the SAME
step any other multi-relation problem uses.

Run:  python3 examples/chase_v2.py   (repo root, package installed)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", ".."))

from openverifiers import (Quantity, Vector3, ThresholdQuery, FactQuery,
                           ExistenceQuery, AggregateQuery)
from openverifiers.v2 import Registry, submit, run_trace, parse_dsl
from openverifiers.domains.physics import Position, Velocity, Acceleration
from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared)
from openverifiers.domains.algebra import ALGEBRA
from openverifiers.domains.physics_primitives import PRIMITIVES
from openverifiers.scenes import Scene


def make_chase_scene(name, *, deer_start_m, deer_speed_mps, tiger_accel_mps2,
                     run_m, v0_mps=0.0, t0_s=0.0) -> Scene:
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
    s.add(Quantity(value=v0_mps, unit=MeterPerSecond(), id="v0"))
    s.add(Quantity(value=0.0, unit=Meter(), id="zero"))
    s.ground_time(t0_s)
    return s


TARGET = AggregateQuery({
    "survival": ThresholdQuery("deer_position", min=400.0),
    "catch_time_ok": FactQuery("catch_time", 20.0),
    "has_velocity": ExistenceQuery("deer.speed"),
    "frame_clock": ExistenceQuery("ground.time"),
})

TRACE = """
# deer: s = 100 + 5t   (uniform velocity, expression in t)
sd = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed)
# tiger: s = 1/2 a t^2 (from rest, expression in t)
st = kin.suvat_s_ut_athalf(u=v0, a=tiger.a)
# generic equate closes the shared unknown -- no bespoke catch-time class
catch_time = alg.equate(a=sd, b=st) with variable=t
deer_position = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed, t=catch_time)
t_haven = kin.suvat_s_s0_vt(s0=zero, v=deer.speed, s=run)
"""


def _registry():
    return Registry([ALGEBRA, PRIMITIVES])


if __name__ == "__main__":
    scene = make_chase_scene("demo", deer_start_m=100.0, deer_speed_mps=5.0,
                             tiger_accel_mps2=1.0, run_m=300.0)
    r = run_trace(_registry(), scene.to_context(), parse_dsl(TRACE))
    print(r.render())
    from openverifiers.v2 import submit as _submit
    res = _submit(TARGET, traces=TRACE, grammars=[ALGEBRA, PRIMITIVES],
                  background=scene.to_context())
    print(f"subchecks: { {s[0]: s[1] for s in res['mission']['subchecks']} }")
    print(f"mission verdict: {res['verdict']}")