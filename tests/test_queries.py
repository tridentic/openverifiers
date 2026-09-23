from openverifiers import (ActionFact, AggregateQuery, ConditionController, ConditionQuery, ExistenceQuery, FactQuery, Premise, Quantity, Query, Specifier, ThresholdQuery, equality_solve)

from openverifiers.domains.units_si import (Meter, MeterPerSecond, MeterPerSecondSquared, Second)
"""Specifier + Query sprint (rev 2): label-bound queries, AggregateQuery,
single-use Specifier, and the chase problem built in-place as a permanent
regression test.
"""

import sympy as sp

import pytest
from dataclasses import FrozenInstanceError
from pydantic_core import ValidationError

from openverifiers.domains.physics import SAVG
from openverifiers.controllers import ConditionController
from openverifiers.domains.coding import Action, default_conditions


# ---------------------------------------------------------------------------
# Chase staging — equations constructed IN-PLACE (never library content)
# ---------------------------------------------------------------------------
def _chase_stage():
    """Chase staged from TWO TRUSTED relations composed by equality_solve —
    no hand-written scenario equation anywhere."""
    from openverifiers.controllers import equality_solve
    from openverifiers.domains.physics import SUT, CONST_V_POS
    D0 = Quantity(value=100.0, unit=Meter(), id="d0")
    V = Quantity(value=5.0, unit=MeterPerSecond(), id="v")
    A = Quantity(value=1.0, unit=MeterPerSecondSquared(), id="a")
    RUN = Quantity(value=300.0, unit=Meter(), id="run")
    T0 = Quantity(value=0.0, unit=MeterPerSecond(), id="v0")
    t_haven = SAVG.solve_for("t", u=V, v=V, s=RUN)
    t_catch = equality_solve(CONST_V_POS, SUT, "t",
                             a_inputs={"s0": D0, "v": V},
                             b_inputs={"u": T0, "a": A})
    deer_at = CONST_V_POS.solve_for("s", s0=D0, v=V, t=t_catch)
    return t_haven, t_catch, deer_at, D0, V, A, RUN, T0


# ---------------------------------------------------------------------------
# Premise immutability + label uniqueness
# ---------------------------------------------------------------------------
def test_premise_field_reassignment_raises():
    premise = Premise.of()
    with pytest.raises(FrozenInstanceError):
        premise.facts = (("x", Quantity(value=1.0, unit=Meter())),)


def test_premise_contained_fact_mutation_raises():
    fact = Quantity(value=3.0, unit=Meter())
    premise = Premise.of(facts={"q": fact})
    with pytest.raises(ValidationError):
        premise.fact("q").value = 5.0


def test_duplicate_label_raises_at_construction():
    # NOTE: a Python dict literal cannot hold two identical keys — same-map
    # duplicates are unrepresentable, which is itself the protection. The
    # real duplicate surface is ACROSS maps (a label colliding between facts
    # and derived), and that must raise:
    a = Quantity(value=1.0, unit=Meter())
    c = Quantity(value=3.0, unit=Meter())
    with pytest.raises(ValueError, match="duplicate premise label 'q'"):
        Premise.of(facts={"q": a}, derived={"q": c})


# ---------------------------------------------------------------------------
# FactQuery — label-bound, pass and fail
# ---------------------------------------------------------------------------
def test_factquery_pass():
    pos = Quantity(value=200.0, unit=Meter(), id="s")
    result = Specifier(Premise.of(facts={"pos": pos}),
                       FactQuery("pos", 200.0)).verify()
    assert result.verdict == "pass"


def test_factquery_fail():
    pos = Quantity(value=200.0, unit=Meter(), id="s")
    result = Specifier(Premise.of(facts={"pos": pos}),
                       FactQuery("pos", 250.0)).verify()
    assert result.verdict == "fail"
    assert result.summary()["coverage"] == {"resolved": 1, "declared": 1}


def test_factquery_unknown_fact_is_inapplicable():
    unknown = Quantity(value=None, unit=Meter(), status="unknown", id="s")
    result = Specifier(Premise.of(facts={"s": unknown}),
                       FactQuery("s", 200.0)).verify()
    assert result.verdict == "inapplicable"
    assert "s" in result.unverifiable_claims


# ---------------------------------------------------------------------------
# BUG-1 REGRESSION — the label collision that sank bare-name lookup
# ---------------------------------------------------------------------------
def test_label_collision_regression_both_derived_t_facts_resolve_distinctly():
    """t_haven and t_catch BOTH carry internal id 't' (their solve-for
    variable). The old name-based lookup found the wrong one. Labels must
    disambiguate, and the provenance walk must still accept the chain."""
    t_haven, t_catch, deer_at, D0, V, A, RUN, T0 = _chase_stage()
    assert t_haven.id == "t" and t_catch.id == "t"   # the collision exists
    premise = Premise.of(
        facts={"d0": D0, "v": V, "a": A, "run": RUN, "v0": T0},
        derived={"haven_time": t_haven, "catch_time": t_catch,
                 "deer_position": deer_at})
    assert Specifier(premise, FactQuery("catch_time", 20.0)).verify().verdict == "pass"
    assert Specifier(premise, FactQuery("haven_time", 60.0)).verify().verdict == "pass"
    assert Specifier(premise, FactQuery("catch_time", 99.0)).verify().verdict == "fail"


# ---------------------------------------------------------------------------
# ThresholdQuery — pass/fail/bounds
# ---------------------------------------------------------------------------
def test_thresholdquery_pass_within_bounds():
    dosage = Quantity(value=15.0, unit=MeterPerSecond(), id="dose")
    result = Specifier(Premise.of(facts={"dose": dosage}),
                       ThresholdQuery("dose", min=10.0, max=20.0)).verify()
    assert result.verdict == "pass"


def test_thresholdquery_fail_above_max():
    dosage = Quantity(value=25.0, unit=MeterPerSecond(), id="dose")
    result = Specifier(Premise.of(facts={"dose": dosage}),
                       ThresholdQuery("dose", max=20.0)).verify()
    assert result.verdict == "fail"


def test_thresholdquery_unknown_is_inapplicable():
    unknown = Quantity(value=None, unit=MeterPerSecond(), status="unknown", id="dose")
    result = Specifier(Premise.of(facts={"dose": unknown}),
                       ThresholdQuery("dose", max=20.0)).verify()
    assert result.verdict == "inapplicable"
    assert "dose" in result.unverifiable_claims


# ---------------------------------------------------------------------------
# ExistenceQuery — pass/fail/unknown
# ---------------------------------------------------------------------------
def test_existencequery_pass():
    approval = ActionFact(id="approval", kind="approval", value=True)
    result = Specifier(Premise.of(facts={"approval": approval}),
                       ExistenceQuery("approval")).verify()
    assert result.verdict == "pass"


def test_existencequery_fail_absent():
    result = Specifier(Premise.of(), ExistenceQuery("approval")).verify()
    assert result.verdict == "fail"


def test_existencequery_present_but_unknown_inapplicable():
    unknown = ActionFact(id="approval", kind="approval", value=None,
                         status="unknown")
    result = Specifier(Premise.of(facts={"approval": unknown}),
                       ExistenceQuery("approval")).verify()
    assert result.verdict == "inapplicable"


# ---------------------------------------------------------------------------
# ConditionQuery — pass/fail/inapplicable (interface conformance)
# ---------------------------------------------------------------------------
CTRL = ConditionController("coding-invariants", default_conditions())


def _act(seq, type_, params=None, pre=()):
    return Action(seq=seq, type=type_, params=params or {}, pre_facts=tuple(pre))


def test_conditionquery_pass():
    actions = [_act(1, "auth_check", {"user": "svc"}),
               _act(2, "db_write", {"file": "db.py"})]
    result = Specifier(Premise.of(), ConditionQuery(CTRL, actions)).verify()
    assert result.verdict == "pass"


def test_conditionquery_fail():
    actions = [_act(1, "db_write", {"file": "db.py"})]
    result = Specifier(Premise.of(), ConditionQuery(CTRL, actions)).verify()
    assert result.verdict == "fail"


def test_conditionquery_inapplicable_on_unknown():
    pre = (ActionFact(id="dep", kind="has_active_dependency", of="rec-7",
                      value=None, status="unknown"),)
    actions = [_act(1, "delete_record", {"record": "rec-7"}, pre=pre)]
    result = Specifier(Premise.of(), ConditionQuery(CTRL, actions)).verify()
    assert result.verdict == "inapplicable"


# ---------------------------------------------------------------------------
# BUG-2 — AggregateQuery: one target, every sub-check visible
# ---------------------------------------------------------------------------
def test_aggregate_chase_single_target_reports_every_subcheck():
    t_haven, t_catch, deer_at, D0, V, A, RUN, T0 = _chase_stage()
    premise = Premise.of(facts={"d0": D0, "v": V, "a": A, "run": RUN,
                                "v0": T0},
                         derived={"haven_time": t_haven, "catch_time": t_catch,
                                  "deer_position": deer_at})
    target = AggregateQuery({
        "survival": ThresholdQuery("deer_position", min=400.0),   # must reach
        "catch_time_ok": FactQuery("catch_time", 20.0),
        "position_derived": ExistenceQuery("deer_position"),
    })
    one = Specifier(premise, target)
    verdict = one.verify()

    assert verdict.verdict == "fail"                 # survival fails
    seen = {item[0]: item[1] for item in verdict.subchecks}
    assert seen == {
        "survival": "fail",                          # 200 < 400 — not at haven
        "catch_time_ok": "pass",
        "position_derived": "pass",
    }
    # the caller sees BOTH verdict kinds: no failure is silently droppable
    assert len(verdict.subchecks) == 3


def test_specifier_is_single_use():
    q = Quantity(value=1.0, unit=Meter(), id="x")
    spec = Specifier(Premise.of(facts={"x": q}), ExistenceQuery("x"))
    assert spec.verify().verdict == "pass"
    with pytest.raises(RuntimeError, match="single-use"):
        spec.verify()                                 # same target: still refused


# ---------------------------------------------------------------------------
# Four-part output + stubs
# ---------------------------------------------------------------------------
def test_verdict_is_four_part_with_null_residue_and_diagnostics():
    pos = Quantity(value=200.0, unit=Meter(), id="s")
    v = Specifier(Premise.of(facts={"pos": pos}),
                  ThresholdQuery("pos", max=400.0)).verify()
    s = v.summary()
    assert s["statistical_residue"] is None
    assert s["coverage_ratio"] == 1.0
    assert "pos == 200.0" in s["reason"]
    assert "canonical" in s["reason"]


def test_stubbed_queries_raise_not_implemented():
    from openverifiers.queries import (InvariantQuery, ConsistencyQuery,
                                       ProvenanceQuery, CompletenessQuery,
                                       ComparativeQuery, CounterfactualQuery)
    for cls in (InvariantQuery, ConsistencyQuery, ProvenanceQuery,
                CompletenessQuery, ComparativeQuery, CounterfactualQuery):
        with pytest.raises(NotImplementedError):
            cls().evaluate(Premise.of())


# ---------------------------------------------------------------------------
# Chase problem — permanent regression (in-place equations, aggregate target)
# ---------------------------------------------------------------------------
def test_chase_pursuit_deer_caught_permanent():
    t_haven, t_catch, deer_at, D0, V, A, RUN, T0 = _chase_stage()
    assert t_haven.value == pytest.approx(60.0)
    assert t_catch.value == pytest.approx(20.0)
    assert deer_at.value == pytest.approx(200.0)

    premise = Premise.of(facts={"d0": D0, "v": V, "a": A, "run": RUN,
                                "v0": T0},
                         derived={"haven_time": t_haven, "catch_time": t_catch,
                                  "deer_position": deer_at})
    verdict = Specifier(premise, AggregateQuery({
        "survival": ThresholdQuery("deer_position", min=400.0),
        "catch_time_ok": FactQuery("catch_time", 20.0),
        "position_derived": ExistenceQuery("deer_position"),
    })).verify()
    assert verdict.verdict == "fail"     # the deer dies: caught at 200 < 400
    assert {item[0]: item[1] for item in verdict.subchecks} == {
        "survival": "fail", "catch_time_ok": "pass", "position_derived": "pass",
    }