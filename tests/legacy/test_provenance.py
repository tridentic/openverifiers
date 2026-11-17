from openverifiers.legacy import (DerivationRecord, EquationController, FactQuery, Premise, Quantity, Specifier, equality_solve)

from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond, MeterPerSecondSquared, Second)
"""Provenance enforcement — the ad-hoc-fact gap, closed and proven closed.

Every test here asserts the SPECIFIC rejection reason string, not merely that
"something raised" or "verdict == fail".
"""

import sympy as sp

import pytest

from openverifiers.legacy.domains.physics import SAVG
from openverifiers.legacy.controllers import EquationController


# --- shared chase staging (two TRUSTED relations composed; explicit ids) ----
def _chase_facts():
    from openverifiers.legacy.controllers import equality_solve
    from openverifiers.legacy.domains.physics import SUT, CONST_V_POS
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
    return Premise.of(facts={"d0": D0, "v": V, "a": A, "run": RUN, "v0": T0},
                      derived={"haven_time": t_haven, "catch_time": t_catch,
                               "deer_position": deer_at})


def _bare_quantity(value, unit, fact_id):
    """Construct a fact WITHOUT any controller and WITHOUT given=True."""
    return Quantity(value=value, unit=unit, id=fact_id)


# ---------------------------------------------------------------------------
# The negative test the prompt demands
# ---------------------------------------------------------------------------
def test_negative_unprovenanced_fact_rejected_with_reason():
    bogus = _bare_quantity(200.0, Meter(), "s")      # hand-built, no controller
    premise = Premise.of(derived={"pos": bogus})
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()

    assert verdict.verdict == "fail"
    assert verdict.reason == "unprovenanced fact: pos"


def test_given_boundary_fact_is_trusted():
    given = _bare_quantity(200.0, Meter(), "s")
    premise = Premise.of(facts={"pos": given})        # given=True forced here
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()
    assert verdict.verdict == "pass"


def test_macro_is_not_a_bypass():
    """Quantity.from_str constructs a fact proof-block; dropping it into
    derived= must fail provenance, exactly like any other bare fact."""
    macro = Quantity.from_str("200 m", id="s")
    premise = Premise.of(derived={"pos": macro})
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()
    assert verdict.verdict == "fail"
    assert verdict.reason == "unprovenanced fact: pos"


# ---------------------------------------------------------------------------
# Registrar checks — controller/rule must really exist
# ---------------------------------------------------------------------------
def test_unregistered_controller_rejected_with_reason():
    forged = _bare_quantity(200.0, Meter(), "s").model_copy(update={
        "derivation": DerivationRecord(controller_name="ghost-controller",
                                       rule_name="solve_for(s)")})
    premise = Premise.of(derived={"pos": forged})
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()
    assert verdict.verdict == "fail"
    assert "not registered" in verdict.reason
    assert "ghost-controller" in verdict.reason


def test_unregistered_rule_rejected_with_reason():
    from openverifiers.legacy.domains.physics import CONST_V_POS
    forged = _bare_quantity(200.0, Meter(), "s").model_copy(update={
        "derivation": DerivationRecord(controller_name=CONST_V_POS.name,
                                       rule_name="solve_for(zzz)")})
    premise = Premise.of(derived={"pos": forged})
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()
    assert verdict.verdict == "fail"
    assert "not a registered rule" in verdict.reason
    assert "solve_for(zzz)" in verdict.reason


def test_input_missing_from_premise_rejected():
    staged = _bare_quantity(200.0, Meter(), "s").model_copy(update={
        "derivation": DerivationRecord(controller_name="equality_solve",
                                       rule_name="equality_solve",
                                       input_fact_ids=("not-in-premise",))})
    premise = Premise.of(derived={"pos": staged})     # givens side empty
    verdict = Specifier(premise, FactQuery("pos", 200.0)).verify()
    assert verdict.verdict == "fail"
    assert "not in the premise" in verdict.reason


# ---------------------------------------------------------------------------
# Legitimate chains pass — including the shared-`t` collision case
# ---------------------------------------------------------------------------
def test_legitimate_chain_passes_and_is_invisible_to_correct_usage():
    premise = _chase_facts()
    verdict = Specifier(premise, FactQuery("catch_time", 20.0)).verify()
    assert verdict.verdict == "pass"
    assert "catch_time == 20.0" in verdict.reason   # query reason, not a
                                                    # provenance complaint


def test_transitive_gate_catches_middle_of_chain():
    premise = _chase_facts()
    # strip the provenance from the MIDDLE fact: catch_time feeds deer_position
    stripped = premise.fact("catch_time").model_copy(update={"derivation": None})
    tampered = Premise.of(
        facts={label: f for label, f in
               dict(premise.facts).items()},
        derived={"haven_time": premise.fact("haven_time"),
                 "catch_time": stripped,
                 "deer_position": premise.fact("deer_position")})
    verdict = Specifier(tampered, FactQuery("deer_position", 200.0)).verify()
    assert verdict.verdict == "fail"
    assert "unprovenanced fact: catch_time" in verdict.reason


# ---------------------------------------------------------------------------
# Given facts are honored as the single trust boundary
# ---------------------------------------------------------------------------
def test_given_facts_resolve_the_provenance_chain():
    premise = _chase_facts()
    for label in ("d0", "v", "a", "run"):
        assert premise.fact(label).given is True
    for label in ("haven_time", "catch_time", "deer_position"):
        f = premise.fact(label)
        assert f.given is False and f.derivation is not None


def test_duplicate_premise_label_raises_at_construction():
    f1 = _bare_quantity(1.0, Meter(), "x")
    f2 = _bare_quantity(2.0, Meter(), "y")
    # same-map duplicates are unrepresentable in a Python dict (keys collapse
    # silently at literal time); the real surface is ACROSS maps:
    with pytest.raises(ValueError, match="duplicate premise label 't'"):
        Premise.of(facts={"t": f1}, derived={"t": f2})