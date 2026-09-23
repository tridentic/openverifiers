from openverifiers import (AggregateQuery, ExistenceQuery, FactQuery, Premise, Quantity, Specifier, ThresholdQuery, Vector3, VerifierContext, equality_solve)

from openverifiers.domains.physics import (Acceleration, PointObject, Position, ReferenceFrame, Time, Velocity)
from openverifiers.domains.units_si import (Meter, MeterPerSecond, MeterPerSecondSquared, Second)
"""Task 6 — VerifierContext: thin wrapper over Premise + Specifier."""

import pytest

from openverifiers.domains.physics import SAVG, SUT, CONST_V_POS
import openverifiers.queries as queries  # for the delegation proof


def test_context_records_constructions_and_solves():
    with VerifierContext() as ctx:
        ground = ReferenceFrame(name="ground")
        deer = PointObject(name="deer", frame=ground)
        with deer.relative_to(ground):
            deer.position = Position(value=Vector3.x_only(100.0, Meter()),
                                     unit=Meter())
            deer.velocity = Velocity(value=Vector3.x_only(5.0,
                                                          MeterPerSecond()),
                                     unit=MeterPerSecond())
        run = Quantity(value=300.0, unit=Meter(), id="run")
        t_haven = SAVG.solve_for("t", u=deer.velocity, v=deer.velocity,
                                 s=run, axis=0)
    ids = {id(x) for x in ctx.facts()}
    assert id(deer) in ids and id(run) in ids and id(t_haven) in ids
    assert any(isinstance(x, Position) for x in ctx.facts())


def test_context_verify_delegates_to_specifier_and_matches_manual():
    with VerifierContext() as ctx:
        ground = ReferenceFrame(name="ground")
        deer = PointObject(name="deer", frame=ground)
        tiger = PointObject(name="tiger", frame=ground)
        with deer.relative_to(ground):
            deer.position = Position(value=Vector3.x_only(100.0, Meter()),
                                     unit=Meter())
            deer.velocity = Velocity(value=Vector3.x_only(5.0,
                                                          MeterPerSecond()),
                                     unit=MeterPerSecond())
        with tiger.relative_to(ground):
            tiger.acceleration = Acceleration(
                value=Vector3.x_only(1.0, MeterPerSecondSquared()),
                unit=MeterPerSecondSquared())
        run = Quantity(value=300.0, unit=Meter(), id="run")
        t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
        t_catch = equality_solve(CONST_V_POS, SUT, "t",
                                 a_inputs={"s0": deer.position,
                                           "v": deer.velocity},
                                 b_inputs={"u": t0, "a": tiger.acceleration},
                                 axis=0)
        target = AggregateQuery({
            "survival": ThresholdQuery("s", min=400.0),
            "catch_time_ok": FactQuery(t_catch, 20.0),
            "has_velocity": ExistenceQuery(deer.velocity),
        })

    # delegation: prove verify() routes through the REAL Specifier
    calls = []
    original = queries.Specifier

    class Spy(original):
        def __init__(self, *a, **k):
            calls.append(1)
            super().__init__(*a, **k)

    queries.Specifier = Spy
    try:
        verdict = ctx.verify(target)
    finally:
        queries.Specifier = original
    assert calls == [1]          # exactly one Specifier build, ours delegated

    # same verdict as the fully manual assembly
    premise = ctx.build_premise()
    manual = original(premise, target).verify()
    assert verdict.verdict == manual.verdict
    assert verdict.summary()["subchecks"] == manual.summary()["subchecks"]
    assert verdict.verdict == "fail"


def test_context_outside_verify_targets_fail_normally():
    """Facts recorded in the ledger are used as-is; an absent target fact
    fails through the normal query path."""
    with VerifierContext() as ctx:
        run = Quantity(value=300.0, unit=Meter(), id="run")
    verdict = ctx.verify(ExistenceQuery("nope"))
    assert verdict.verdict == "fail"


def test_context_chase_numeric_pins():
    """Task 8 permanent pins inside the VerifierContext model: the choreography
    numbers must not drift (60s haven, 20s catch, 200m position, CAUGHT)."""
    with VerifierContext() as ctx:
        ground = ReferenceFrame(name="ground")
        deer = PointObject(name="deer", frame=ground)
        tiger = PointObject(name="tiger", frame=ground)
        with deer.relative_to(ground):
            deer.position = Position(value=Vector3.x_only(100.0, Meter()),
                                     unit=Meter())
            deer.velocity = Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                                     unit=MeterPerSecond())
        with tiger.relative_to(ground):
            tiger.acceleration = Acceleration(
                value=Vector3.x_only(1.0, MeterPerSecondSquared()),
                unit=MeterPerSecondSquared())
        run = Quantity(value=300.0, unit=Meter(), id="run")
        t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
        t_haven = SAVG.solve_for("t", u=deer.velocity, v=deer.velocity,
                                 s=run, axis=0)
        t_catch = equality_solve(CONST_V_POS, SUT, "t",
                                 a_inputs={"s0": deer.position,
                                           "v": deer.velocity},
                                 b_inputs={"u": t0, "a": tiger.acceleration},
                                 axis=0)
        deer_at = CONST_V_POS.solve_for("s", s0=deer.position,
                                        v=deer.velocity, t=t_catch, axis=0)
        ground.time = Time(value=t_catch.value, unit=Second())
        verdict = ctx.verify(AggregateQuery({
            "survival": ThresholdQuery(deer_at, min=400.0),
            "catch_time_ok": FactQuery(t_catch, 20.0),
            "clock": ExistenceQuery(ground.time),
        }))
    assert t_haven.value == pytest.approx(60.0)
    assert t_catch.value == pytest.approx(20.0)
    assert deer_at.value == pytest.approx(200.0)
    assert ground.time.value == pytest.approx(20.0)
    assert verdict.verdict == "fail"     # caught 200 m short of the haven
    assert {item[0]: item[1] for item in verdict.subchecks} == {
        "survival": "fail", "catch_time_ok": "pass", "clock": "pass",
    }