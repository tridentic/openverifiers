"""v2 domain grammars — one runnable scenario per domain slice."""

from openverifiers import ActionFact, EnumValue, FactQuery
from openverifiers.domains import standard_grammars
from openverifiers.domains.business import money
from openverifiers.domains.english import rule_adapter
from openverifiers.domains.math import make_number
from openverifiers.v2 import Registry, parse_dsl, run_trace, extract_facts

reg = Registry(standard_grammars())


def test_math_arithmetic_and_proof_in_one_trace():
    r = run_trace(reg, reg.facts | {"a": make_number(3, "a"),
                                    "b": make_number(4, "b")},
                  parse_dsl("""
        z = math.mul(a, b)        # 12
        base = proof.base with n=0, expr="2n-1"
        step = proof.step(predecessor=base) with k=0, expr="2n-1"
        f = induction.combine(base=base, step=step) with variable=n, expr="2n-1"
        """))
    assert r.verdict == "pass", r.reason
    assert r.env["z"].value == 12.0
    assert r.env["f"].quantifier == "forall"


def test_law_element_slice():
    bg = {"allegation": ActionFact(
        kind="allegation", of="negligence", value=True)}
    r = run_trace(reg, bg, parse_dsl("""
        duty = law.element_met(allegation) with statute=negligence, element=duty
        breach = law.element_met(allegation) with element=breach
        v = law.all_elements(duty, breach)
        """))
    assert r.verdict == "pass", r.reason
    assert r.env["duty"].value.value == "met"
    assert r.env["v"].value.value == "satisfied"
    assert r.env["duty"].provenance == "extracted"


def test_business_compound():
    r = run_trace(reg, reg.facts | {"p": money(100.0, "p")},
                  parse_dsl("fv = business.compound(principal=p) "
                            "with rate_pct=5, years=2"))
    assert r.verdict == "pass", r.reason
    assert abs(r.env["fv"].value - 110.25) < 1e-9


def test_english_extraction_keeps_tier_visible():
    claims = extract_facts(rule_adapter, "the cat is happy")
    r = run_trace(reg, {"s": claims[0],
                        "o": ActionFact(id="o", kind="claim",
                                        value=EnumValue(enum="relation",
                                                        value="cat is happy"),
                                        of="cat")},
                  parse_dsl("v = english.agreement(subject=s, object=o)"))
    assert r.verdict == "pass", r.reason
    assert r.env["s"].provenance == "extracted"
    assert r.env["v"].value.value == "consistent"


def test_failed_step_trace_marks_verdict_fail():
    # law.element_met without an allegation fails its precondition
    r = run_trace(reg, reg.facts, parse_dsl("duty = law.element_met()"))
    assert r.verdict != "pass"
    assert "allegation" in r.reason