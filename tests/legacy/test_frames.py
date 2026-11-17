"""Object hierarchy + ReferenceFrame + frame-consistency enforcement.
Rebuilt after an import-split accident; content identical to the verified
original (vectors required by Task 1 applied)."""

import pytest

from openverifiers.legacy import Quantity, Vector3
from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared, Kilogram,
                                            Second)
from openverifiers.legacy.domains.physics import (ReferenceFrame, PointObject,
                                           Position, Velocity, Acceleration,
                                           Mass, Time, VUAT)
from openverifiers.legacy.errors import FrameMismatchError

GROUND = ReferenceFrame(name="ground")
SKY = ReferenceFrame(name="sky")


def test_motion_property_requires_frame():
    with pytest.raises(ValueError, match="no active reference frame"):
        Position(value=1.0, unit=Meter())


def test_property_dimension_validator():
    with pytest.raises(ValueError, match="requires a unit of dimension"):
        Position(value=Vector3.x_only(1.0, MeterPerSecond()),
                 unit=MeterPerSecond(), frame=GROUND)
    Mass(value=2.0, unit=Kilogram())


def test_with_block_stamps_frame_by_inspection():
    deer = PointObject(name="deer", frame=GROUND)
    with deer.relative_to(GROUND):
        deer.position = Position(value=Vector3.x_only(100.0, Meter()),
                                 unit=Meter())
        deer.velocity = Velocity(value=Vector3.x_only(5.0, MeterPerSecond()),
                                 unit=MeterPerSecond())
    assert deer.position.frame == GROUND
    assert deer.velocity.frame == GROUND
    assert deer.position.value.x == 100.0


def test_explicit_frame_kwarg_wins_inside_block():
    p = Position(value=Vector3.x_only(3.0, Meter()), unit=Meter(),
                 frame=GROUND)
    assert p.frame == GROUND


def test_with_cannot_reframe_an_object():
    deer = PointObject(name="deer", frame=GROUND)
    with pytest.raises(ValueError, match="cannot reframe"):
        with deer.relative_to(SKY):
            pass


def test_assignment_rejects_frame_takeover():
    deer = PointObject(name="deer", frame=GROUND)
    foreign = Position(value=Vector3.x_only(9.0, Meter()), unit=Meter(),
                       frame=SKY)
    with pytest.raises(ValueError, match="frame mismatch"):
        deer.position = foreign


def test_suvat_rejects_mixed_frames_with_frame_mismatch_reason():
    v_sky = Velocity(value=Vector3.x_only(7.0, MeterPerSecond()),
                     unit=MeterPerSecond(), frame=SKY)
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    with pytest.raises(FrameMismatchError) as err:
        VUAT.solve_for("v", u=v_sky, a=a, t=t, axis=0)
    assert "frame mismatch" in str(err.value)
    assert "ground" in str(err.value) and "sky" in str(err.value)


def test_controller_frame_kwarg_mismatch_fails():
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    u = Velocity(value=Vector3.x_only(4.0, MeterPerSecond()),
                 unit=MeterPerSecond(), frame=GROUND)
    with pytest.raises(FrameMismatchError) as err:
        VUAT.solve_for("v", u=u, a=a, t=t, frame=SKY, axis=0)
    assert "frame mismatch" in str(err.value)
    assert "call declares frame" in str(err.value)


def test_controller_frame_kwarg_matching_passes():
    a = Acceleration(value=Vector3.x_only(2.0, MeterPerSecondSquared()),
                     unit=MeterPerSecondSquared(), frame=GROUND)
    t = Quantity(value=3.0, unit=Second())
    u = Velocity(value=Vector3.x_only(4.0, MeterPerSecond()),
                 unit=MeterPerSecond(), frame=GROUND)
    v = VUAT.solve_for("v", u=u, a=a, t=t, frame=GROUND, axis=0)
    assert v.value == pytest.approx(10.0)


def test_of_objects_derives_attribute_paths_not_user_strings():
    from openverifiers.legacy import Premise, ExistenceQuery, FactQuery, Specifier
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
    premise = Premise.of_objects(deer, tiger)
    assert set(premise.labels()) == {
        "deer.position", "deer.velocity", "tiger.acceleration"}
    assert premise.fact("deer.position").value.x == 100.0
    assert Specifier(premise, ExistenceQuery("deer.position")).verify().verdict == "pass"
    assert Specifier(premise, FactQuery(deer.position,
                                        Vector3.x_only(100.0, Meter()))).verify().verdict == "pass"
    assert Specifier(premise, FactQuery(deer.velocity,
                                        Vector3.x_only(5.0, MeterPerSecond()))).verify().verdict == "pass"


def test_no_active_frame_raises_outside_block():
    with pytest.raises(ValueError, match="no active reference frame"):
        Position(value=Vector3.x_only(1.0, Meter()), unit=Meter())


def test_block_positions_and_stacks_are_context_local():
    deer = PointObject(name="deer", frame=GROUND)
    with deer.relative_to(GROUND):
        p = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter())
        assert p.frame == GROUND
    with pytest.raises(ValueError, match="no active reference frame"):
        Position(value=Vector3.x_only(2.0, Meter()), unit=Meter())


def test_nested_blocks_resolve_to_innermost_frame():
    sky = ReferenceFrame(name="sky")
    deer = PointObject(name="deer", frame=GROUND)
    bird = PointObject(name="bird", frame=sky)
    with deer.relative_to(GROUND):
        with bird.relative_to(sky):
            b = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter())
            assert b.frame == sky
        d = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter())
        assert d.frame == GROUND
    with pytest.raises(ValueError, match="cannot reframe"):
        with deer.relative_to(sky):
            pass


def test_duplicate_object_frames_are_rejected_by_premise():
    from openverifiers.legacy import Premise
    a = PointObject(name="x", frame=GROUND)
    b = PointObject(name="x", frame=GROUND)
    a.position = Position(value=Vector3.x_only(1.0, Meter()), unit=Meter(),
                          frame=GROUND)
    b.position = Position(value=Vector3.x_only(2.0, Meter()), unit=Meter(),
                          frame=GROUND)
    with pytest.raises(ValueError, match="duplicate premise label"):
        Premise.of_objects(a, b)


def test_time_is_owned_by_reference_frame():
    frame = ReferenceFrame(name="clock")
    frame.time = Time(value=20.0, unit=Second())
    assert frame.time.value == 20.0
    assert frame.time.unit.dimension == Second().dimension


def test_time_rejects_non_time_unit():
    with pytest.raises(ValueError, match="Time requires a unit"):
        Time(value=1.0, unit=Meter())


def test_chase_object_model_permanent_regression():
    from openverifiers.legacy import (Premise, FactQuery, ThresholdQuery,
                               ExistenceQuery, AggregateQuery, Specifier,
                               equality_solve)
    from openverifiers.legacy.domains.physics import SAVG, SUT, CONST_V_POS

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
    t_catch = equality_solve(
        CONST_V_POS, SUT, "t",
        a_inputs={"s0": deer.position, "v": deer.velocity},
        b_inputs={"u": t0, "a": tiger.acceleration}, axis=0)
    deer_at = CONST_V_POS.solve_for("s", s0=deer.position,
                                    v=deer.velocity, t=t_catch, axis=0)
    assert t_haven.value == pytest.approx(60.0)
    assert t_catch.value == pytest.approx(20.0)
    assert deer_at.value == pytest.approx(200.0)

    premise = Premise.of_objects(
        deer, tiger, given={"run": run, "v0": t0},
        derived={"catch_time": t_catch, "deer_position": deer_at})
    verdict = Specifier(premise, AggregateQuery({
        "survival": ThresholdQuery("deer_position", min=400.0),
        "catch_time_ok": FactQuery("catch_time", 20.0),
        "has_velocity": ExistenceQuery("deer.velocity"),
    })).verify()
    assert verdict.verdict == "fail"
    assert {item[0]: item[1] for item in verdict.subchecks} == {
        "survival": "fail", "catch_time_ok": "pass", "has_velocity": "pass",
    }