"""One passing and one failing test per kernel rule (see kernel/check.py)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from openverifiers.m1.kernel import (
    DomainPack,
    Fact,
    FactType,
    Proof,
    Provenance,
    Requirement,
    Selector,
    Step,
    Transformation,
    Verdict,
    check,
)

from .toy_pack import PACK, num

A, B = num("a", 2), num("b", 3)


def req(fact_id: str | None = None, pred: str = "exists", where: dict[str, Any] | None = None,
        **args: Any) -> Requirement:
    return Requirement(id=f"r_{fact_id or 'q'}", selector=Selector(fact_id, where or {}),
                       predicate=pred, args=args)


def add(sid: str, a: str, b: str, out: str, value: Any) -> Step:
    return Step(sid, "add", {"a": a, "b": b}, {"sum": num(out, value)})


def run(steps: Sequence[Step], reqs: Sequence[Requirement] = (),
        facts: Sequence[Fact] = (A, B), pack: DomainPack = PACK) -> Verdict:
    return check(facts, reqs, Proof(tuple(steps)), pack)


def codes(v: Verdict) -> list[str]:
    return [f.code for f in v.failures]


# ---- happy path -----------------------------------------------------------

def test_valid_chain_is_fully_hard() -> None:
    v = run([add("s1", "a", "b", "c", 5), add("s2", "c", "c", "d", 10)], [req("d", "equals",
                                                                            value=10)])
    assert v.valid and v.trust_grade == "fully_hard" and v.failures == ()
    assert v.support == ("s1", "s2")


def test_steps_may_be_listed_in_any_order() -> None:
    v = run([add("s2", "c", "c", "d", 10), add("s1", "a", "b", "c", 5)], [req("d")])
    assert v.valid
    assert [e.subject for e in v.trace if e.kind == "step"] == ["s1", "s2"]


# ---- structure -------------------------------------------------------------

def test_duplicate_initial_fact_id() -> None:
    assert run([], facts=(A, B)).valid
    v = run([], facts=(A, num("a", 9)))
    assert codes(v) == ["duplicate_fact_id"] and v.trust_grade == "invalid"


def test_duplicate_child_fact_id() -> None:
    parent = Fact("p", "note", children=(num("a", 1),))
    assert run([], facts=(Fact("p", "note", children=(num("k", 1),)),)).valid
    assert codes(run([], facts=(A, parent))) == ["duplicate_fact_id"]


def test_duplicate_step_id() -> None:
    v = run([add("s1", "a", "b", "c", 5), add("s1", "a", "a", "e", 4)])
    assert "duplicate_step_id" in codes(v)


def test_output_may_not_redefine_an_established_fact() -> None:
    v = run([add("s1", "a", "b", "a", 5)])
    assert codes(v) == ["duplicate_fact_id"] and v.failures[0].step_id == "s1"


def test_two_steps_may_not_produce_the_same_fact() -> None:
    v = run([add("s1", "a", "b", "c", 5), add("s2", "a", "a", "c", 4)])
    assert codes(v) == ["duplicate_fact_id"] and v.failures[0].step_id == "s2"


def test_output_may_fill_a_target_slot() -> None:
    slot = num("c", status="target")
    v = run([add("s1", "a", "b", "c", 5)], [req("c", "equals", value=5)], facts=(A, B, slot))
    assert v.valid


def test_unregistered_fact_type() -> None:
    v = run([], facts=(Fact("x", "vector", value=1),))
    assert codes(v) == ["unknown_fact_type"]


def test_fact_type_validator() -> None:
    assert codes(run([], facts=(num("x", "seven"),))) == ["invalid_fact"]
    assert codes(run([add("s1", "a", "b", "c", "five")])) == ["invalid_fact"]


def test_unknown_fact_must_say_why() -> None:
    assert run([], facts=(num("x", status="unknown", why_unknown="not measured"),)).valid
    assert codes(run([], facts=(num("x", status="unknown"),))) == ["invalid_fact"]


def test_initial_fact_cannot_claim_derived() -> None:
    assert codes(run([], facts=(num("x", 1, status="derived"),))) == ["invalid_fact"]


def test_unknown_transformation() -> None:
    v = run([Step("s1", "teleport", {"x": "a"}, {"y": num("y", 1)})])
    assert codes(v) == ["unknown_transformation"]


def test_missing_input() -> None:
    v = run([add("s1", "a", "zzz", "c", 5)])
    f = v.failures[0]
    assert f.code == "missing_input" and f.facts == ("zzz",) and f.step_id == "s1"


def test_cycle_is_rejected_and_downstream_steps_are_skipped() -> None:
    steps = [add("s1", "a", "d", "c", 5), add("s2", "c", "b", "d", 8),
             add("s3", "d", "d", "e", 16)]
    v = run(steps)
    assert "cycle" in codes(v)
    status = {e.subject: e.status for e in v.trace if e.kind == "step"}
    assert status == {"s1": "rejected", "s2": "rejected", "s3": "skipped"}


def test_self_loop_is_a_cycle() -> None:
    assert "cycle" in codes(run([add("s1", "a", "c", "c", 5)]))


# ---- steps -------------------------------------------------------------------

def test_failed_step_skips_dependents() -> None:
    v = run([add("s1", "a", "b", "c", 6), add("s2", "c", "c", "d", 12)])
    assert codes(v) == ["output_mismatch", "dependency_failed"]
    assert v.failures[1].step_id == "s2"


def test_input_and_output_roles_must_match_signature() -> None:
    assert codes(run([Step("s1", "add", {"a": "a"}, {"sum": num("c", 2)})])) == [
        "input_role_mismatch"]
    assert codes(run([Step("s1", "add", {"a": "a", "b": "b"}, {"total": num("c", 5)})])) == [
        "output_role_mismatch"]


def test_input_type_must_match() -> None:
    note = Fact("n", "note", value="hi")
    v = run([add("s1", "a", "n", "c", 5)], facts=(A, note))
    assert codes(v) == ["input_type_mismatch"]
    assert run([Step("s1", "annotate", {"x": "n"},
                     {"n": Fact("m", "note", value="saw n")})], facts=(note,)).valid


def test_output_type_must_match() -> None:
    v = run([Step("s1", "add", {"a": "a", "b": "b"}, {"sum": Fact("c", "note", value=5)})])
    assert codes(v) == ["output_mismatch"]


def test_target_input_is_not_established() -> None:
    v = run([add("s1", "a", "t", "c", 5)], facts=(A, num("t", status="target")))
    assert codes(v) == ["input_not_established"] and v.trust_grade == "invalid"


def test_unknown_input_makes_verdict_undetermined() -> None:
    u = num("u", status="unknown", why_unknown="sensor offline", evidence_needed=("reading",))
    v = run([add("s1", "a", "u", "c", 5)], [req("c")], facts=(A, u, num("c", status="target")))
    assert codes(v) == ["input_unknown", "requirement_not_reached"]
    assert v.trust_grade == "undetermined" and not v.valid
    assert "reading" in v.failures[0].message


def test_precondition() -> None:
    assert run([Step("s1", "sqrt", {"x": "a"}, {"y": num("y", 2 ** 0.5)})]).valid
    v = run([Step("s1", "sqrt", {"x": "n"}, {"y": num("y", 1)})], facts=(num("n", -1),))
    f = v.failures[0]
    assert (f.code, f.precondition, f.step_id) == ("precondition_failed", "nonnegative", "s1")


def test_precondition_that_raises_fails_closed() -> None:
    v = run([Step("s1", "explode", {"x": "a"}, {"y": num("y", 2)})])
    assert codes(v) == ["precondition_failed"] and "boom" in v.failures[0].message


def test_claimed_output_is_recomputed() -> None:
    v = run([add("s1", "a", "b", "c", -5)])
    assert codes(v) == ["output_mismatch"] and v.failures[0].facts == ("c",)


def test_accepted_state_holds_recomputed_value_not_claim() -> None:
    v = run([add("s1", "a", "b", "c", 5.0000000000001)], [req("c", "equals", value=5)])
    assert v.valid  # within tolerance; state value is the recomputed 5


def test_effect_error_fails_closed() -> None:
    assert codes(run([Step("s1", "broken", {"x": "a"}, {"y": num("y", 1)})])) == ["effect_error"]


def test_checker_only_transformation() -> None:
    assert run([Step("s1", "succ", {"x": "a"}, {"y": num("y", 3)})]).valid
    v = run([Step("s1", "succ", {"x": "a"}, {"y": num("y", 4)})])
    assert codes(v) == ["checker_rejected"] and "hard checker" in v.failures[0].message


def test_checker_error_fails_closed() -> None:
    v = run([Step("s1", "crashy_check", {"x": "a"}, {"y": num("y", 1)})])
    assert codes(v) == ["checker_error"]


def test_grounded_step_needs_existing_citation() -> None:
    cited = num("c", 3, provenance=Provenance("llm", citation="table"))
    v = run([Step("s1", "lookup", {}, {"value": cited})], [req("c")])
    assert v.valid and v.trust_grade == "grounded"
    bogus = num("c", 3, provenance=Provenance("llm", citation="made-up"))
    v = run([Step("s1", "lookup", {}, {"value": bogus})])
    assert codes(v) == ["checker_rejected"]  # pack checker sees no source text first


def test_grounded_citation_checked_by_kernel_even_if_checker_is_lax() -> None:
    lax = Transformation("lookup", "grounded", {}, {"value": "num"},
                         checker=lambda i, p, o: None)
    pack = DomainPack("lax", PACK.fact_types, {"lookup": lax}, sources={"table": "c = 3"})
    v = run([Step("s1", "lookup", {}, {"value": num("c", 3)})], pack=pack)
    assert codes(v) == ["citation_missing"]


def test_soft_step_in_support_makes_result_conditional() -> None:
    v = run([Step("s1", "guess", {"x": "a"}, {"y": num("y", 7)})], [req("y")])
    assert v.valid and v.trust_grade == "conditional_on_soft_steps" and v.soft_steps == ("s1",)


def test_soft_step_outside_support_does_not_taint() -> None:
    v = run([Step("s1", "guess", {"x": "a"}, {"y": num("y", 7)}), add("s2", "a", "b", "c", 5)],
            [req("c")])
    assert v.trust_grade == "fully_hard" and v.soft_steps == ()


def test_unverified_input_makes_result_conditional() -> None:
    v = run([add("s1", "a", "b", "c", 5)], [req("c")], facts=(A, num("b", 3, status="unverified")))
    assert v.trust_grade == "conditional_on_unverified_facts" and v.unverified_facts == ("b",)


# ---- requirements --------------------------------------------------------------

def test_requirement_by_attribute() -> None:
    tagged = num("x", 1, attributes={"role": "answer"})
    assert run([], [req(where={"role": "answer"})], facts=(A, tagged)).valid
    v = run([], [req(where={"role": "answer"})], facts=(num("y", 2, attributes={"role": "answer"}),
                                                         tagged))
    assert codes(v) == ["requirement_ambiguous"] and set(v.failures[0].facts) == {"x", "y"}


def test_requirement_by_own_fields() -> None:
    assert run([], [req(where={"type": "num", "owner": "car"})],
               facts=(A, num("v", 1, owner="car"))).valid


def test_requirement_unmatched() -> None:
    assert codes(run([], [req("nope")])) == ["requirement_unmatched"]


def test_requirement_target_not_reached() -> None:
    v = run([], [req("c")], facts=(A, num("c", status="target")))
    assert codes(v) == ["requirement_not_reached"] and v.trust_grade == "invalid"


def test_requirement_on_unknown_is_undetermined() -> None:
    v = run([], [req("u")], facts=(num("u", status="unknown", why_unknown="?"),))
    assert codes(v) == ["requirement_unknown"] and v.trust_grade == "undetermined"


def test_equals_predicate() -> None:
    assert run([], [req("a", "equals", value=2)]).valid
    assert codes(run([], [req("a", "equals", value=3)])) == ["requirement_failed"]
    assert codes(run([], [req("a", "equals")])) == ["requirement_failed"]


def test_pack_predicate() -> None:
    assert run([], [req("a", "positive")]).valid
    assert codes(run([], [req("n", "positive")], facts=(num("n", -1),))) == ["requirement_failed"]


def test_unknown_and_crashing_predicates() -> None:
    assert codes(run([], [req("a", "prime")])) == ["unknown_predicate"]
    assert codes(run([], [req("a", "crashes")])) == ["requirement_failed"]


def test_requirement_can_select_a_child_fact() -> None:
    parent = Fact("p", "note", children=(num("k", 4),))
    assert run([], [req("k", "equals", value=4)], facts=(parent,)).valid


# ---- domain pack construction ------------------------------------------------

def test_pack_cannot_redefine_builtin_predicates() -> None:
    with pytest.raises(ValueError, match="built-in"):
        DomainPack("x", {}, {}, predicates={"equals": lambda f, a: None})


def test_pack_rejects_unregistered_types_in_signatures() -> None:
    t = Transformation("t", "hard", {"x": "matrix"}, {"y": "num"}, effect=lambda i, p: {})
    with pytest.raises(ValueError, match="unregistered type"):
        DomainPack("x", {"num": FactType("num")}, {"t": t})


def test_transformation_needs_effect_or_checker() -> None:
    with pytest.raises(ValueError, match="neither an effect nor a checker"):
        Transformation("t", "hard", {}, {"y": "num"})


def test_transformation_tier_is_closed() -> None:
    with pytest.raises(ValueError, match="tier"):
        Transformation("t", "vibes", {}, {"y": "num"}, effect=lambda i, p: {})  # type: ignore[arg-type]
