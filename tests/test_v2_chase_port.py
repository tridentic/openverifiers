"""Chase port parity — the v1 pursuit example on the v2 primitive set.

Same numbers the v1 chase.py produced (and the old bespoke-grammar port):
catch 20 s, deer at catch 200 m, same mission verdicts — but every step is a
registered syllabus relation and composition happens in the TRACE.
"""

from openverifiers import (Quantity, Vector3, ThresholdQuery, FactQuery,
                           ExistenceQuery, AggregateQuery)
from openverifiers.v2 import submit
from openverifiers.domains.physics import Position, Velocity, Acceleration
from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared)
from openverifiers.domains.algebra import ALGEBRA
from openverifiers.domains.physics_primitives import PRIMITIVES
from openverifiers.scenes import Scene

TARGET = AggregateQuery({
    "survival": ThresholdQuery("deer_position", min=400.0),
    "catch_time_ok": FactQuery("catch_time", 20.0),
    "has_velocity": ExistenceQuery("deer.speed"),
    "frame_clock": ExistenceQuery("ground.time"),
})

TRACE = """
sd = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed)
st = kin.suvat_s_ut_athalf(u=v0, a=tiger.a)
catch_time = alg.equate(a=sd, b=st) with variable=t
deer_position = kin.suvat_s_s0_vt(s0=deer.start, v=deer.speed, t=catch_time)
t_haven = kin.suvat_s_s0_vt(s0=zero, v=deer.speed, s=run)
"""


def _scene():
    s = Scene("port")
    deer = s.object("deer")
    tiger = s.object("tiger")
    with deer:
        s.add(Position(value=Vector3.x_only(100.0, Meter()), unit=Meter(),
                       frame=s.ground, id="deer.start"))
        s.add(Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                       unit=MeterPerSecond(), frame=s.ground,
                       id="deer.speed"))
    with tiger:
        s.add(Acceleration(
            value=Vector3.x_only(1.0, MeterPerSecondSquared()),
            unit=MeterPerSecondSquared(), frame=s.ground, id="tiger.a"))
    s.add(Quantity(value=300.0, unit=Meter(), id="run"))
    s.add(Quantity(value=0.0, unit=MeterPerSecond(), id="v0"))
    s.add(Quantity(value=0.0, unit=Meter(), id="zero"))
    s.ground_time(0.0)
    return s


def _run():
    return submit(TARGET, traces=TRACE, grammars=[ALGEBRA, PRIMITIVES],
                  background=_scene().to_context())


def test_verdict_parity_with_v1_example():
    r = _run()
    assert r["verdict"] == "fail"          # same as v1 chase.py
    assert {s[0]: s[1] for s in r["mission"]["subchecks"]} == {
        "survival": "fail", "catch_time_ok": "pass",
        "has_velocity": "pass", "frame_clock": "pass"}


def test_numeric_outcomes_match_v1():
    r = _run()
    steps = {s["id"]: s for s in r["traces"][0]["steps"]}
    assert {"catch_time", "deer_position", "t_haven"} <= set(steps)
    assert steps["catch_time"]["status"] == "pass"
    assert steps["deer_position"]["status"] == "pass"


def test_one_primitive_relation_per_registered_name():
    from openverifiers.v2 import Registry
    reg = Registry([ALGEBRA, PRIMITIVES])
    names = set(reg.transforms)
    assert "physics_trace.catch_time" not in names      # bespoke deleted
    assert "kin.suvat_s_s0_vt" in names
    assert "alg.equate" in names


def test_unregistered_relation_name_is_blocked():
    r = submit(TARGET, traces="x = physics_trace.not_a_relation(a)",
               grammars=[ALGEBRA, PRIMITIVES],
               background=_scene().to_context())
    assert r["verdict"] != "pass"
    assert "closed whitelist" in r["reason"]