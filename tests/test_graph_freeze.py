"""Task B/C/D — graph inspection and freeze enforcement."""

import pytest

from openverifiers import (VerifierContext, Quantity, Vector3, ThresholdQuery,
                           ExistenceQuery, AggregateQuery, equality_solve)
from openverifiers.domains.physics import (ReferenceFrame, PointObject,
                                           Position, Velocity, Acceleration,
                                           SUT, CONST_V_POS)
from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared)


def _make_objects(ground):
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
    return deer, tiger


def _catch(deer, tiger, t0):
    """Derivation (post-freeze): composes the two trusted relations."""
    return equality_solve(CONST_V_POS, SUT, "t",
                          a_inputs={"s0": deer.position, "v": deer.velocity},
                          b_inputs={"u": t0, "a": tiger.acceleration},
                          axis=0)


# ---------------------------------------------------------------------------
# Task B — inspectable graph
# ---------------------------------------------------------------------------
def test_graph_nodes_and_edges_and_check():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            deer, tiger = _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        t_catch = _catch(deer, tiger, t0)
        records = ctx.graph.to_records()
        nodes = records["nodes"]
        assert any(n["kind"] == "object" and n["name"] == "deer"
                   for n in nodes)
        derived = [n for n in nodes if n["kind"] == "fact"
                   and n["given"] is False]
        assert derived, "derived facts must appear as non-given nodes"
        assert records["edges"], "a derived node must link to its inputs"
        ok, problems = ctx.graph.check()
        assert ok, problems


def test_graph_check_fails_on_unprovenanced_fact():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            deer, tiger = _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        t_catch = _catch(deer, tiger, t0)
        # a derivation pointing at a controller that does not exist: the
        # graph's static check must catch it (model_copy bypasses the
        # recorder hook so this leaks into the ledger undetected)
        from openverifiers import DerivationRecord
        bogus = t_catch.model_copy(update={
            "id": "bogus",
            "derivation": DerivationRecord(controller_name="ghost-controller",
                                           rule_name="r", input_fact_ids=())})
        ctx._ledger.append(bogus)
        ok, problems = ctx.graph.check()
    assert not ok
    assert any("ghost-controller" in p and "bogus" in p
               for p in problems)


def test_graph_render_is_a_flat_inspectable_view():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            deer, tiger = _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        t_catch = _catch(deer, tiger, t0)
    lines = ctx.graph.render()
    assert any(line.startswith("node ") for line in lines)
    assert any(line.startswith("edge ") for line in lines)
    assert any("derived" in line for line in lines)
    assert any("given" in line for line in lines)


# ---------------------------------------------------------------------------
# Task C/D — freeze
# ---------------------------------------------------------------------------
def test_verify_before_freeze_raises():
    with VerifierContext() as ctx:
        pass
    with pytest.raises(RuntimeError, match="no frozen premise/target"):
        ctx.verify()


def test_given_fact_after_freeze_exits_raises():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        with pytest.raises(RuntimeError, match="no new given facts outside"):
            rogue = Quantity(value=999.0, unit=Meter(), id="rogue")


def test_target_redefinition_after_freeze_raises():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        with pytest.raises(RuntimeError, match="already frozen"):
            ctx.verify(ThresholdQuery("run", min=0.0))


def test_verify_post_freeze_evaluates_frozen_target_only():
    with VerifierContext() as ctx:
        with ctx.freeze():
            ground = ReferenceFrame(name="ground")
            deer, tiger = _make_objects(ground)
            run = Quantity(value=300.0, unit=Meter(), id="run")
            t0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
            target = AggregateQuery({
                "has_velocity": ExistenceQuery("deer.velocity"),
            })
        t_catch = _catch(deer, tiger, t0)
        verdict = ctx.verify()   # no target argument: the frozen one is used
    assert verdict.verdict == "pass"
    assert {item[0]: item[1] for item in verdict.subchecks} == {
        "has_velocity": "pass"}