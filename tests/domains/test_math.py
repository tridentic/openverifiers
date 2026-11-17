from __future__ import annotations

from pathlib import Path

import pytest

from openverifiers.case import load_case
from openverifiers.domains import load
from openverifiers.domains.math import parse_side, quantity, units
from openverifiers.kernel import (
    Fact,
    Proof,
    Provenance,
    Requirement,
    Selector,
    Step,
    Verdict,
    check,
)

PACK = load("math")
CASE_DIR = Path(__file__).resolve().parents[2] / "benchmarks" / "cases" / "math"
CASES = sorted(CASE_DIR.glob("*.json"))


def run(facts: list[Fact], steps: list[Step], reqs: list[Requirement] | None = None) -> Verdict:
    return check(facts, reqs or [], Proof(tuple(steps)), PACK)


def codes(v: Verdict) -> list[str]:
    return [f.code for f in v.failures]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_benchmark_cases_verify(path: Path) -> None:
    c = load_case(path)
    v = check(c.facts, c.requirements, c.proof, PACK)
    assert v.valid, v.failures
    assert v.trust_grade == c.expected["trust_grade"]


def test_unit_parser() -> None:
    assert units.parse("km/h")[0] == pytest.approx(1000 / 3600)
    assert units.dimension("kg*m/s^2") == units.dimension("N")
    assert units.dimension("J") == units.dimension("N*m")
    assert units.si_unit(units.dimension("W")) == "m^2*kg/s^3"
    assert units.si_unit(units.dimension("1")) == "1"
    for bad in ["furlong", "m//s", "*m", "m s"]:
        with pytest.raises(ValueError):
            units.parse(bad)


def test_quantities_compare_across_units() -> None:
    v = run([quantity("d", 1, "km")], [], [Requirement("r", Selector("d"), "equals",
                                                         {"value": 1000, "unit": "m"})])
    assert v.valid
    v = run([quantity("d", 1, "km")], [], [Requirement("r", Selector("d"), "equals",
                                                         {"value": 1000, "unit": "s"})])
    assert codes(v) == ["requirement_failed"]


def test_add_requires_same_dimension() -> None:
    step = Step("s1", "arith.add", {"a": "x", "b": "y"}, {"result": quantity("z", 5, "m")})
    v = run([quantity("x", 2, "m"), quantity("y", 3, "s")], [step])
    assert codes(v) == ["precondition_failed"] and v.failures[0].precondition == "same_dimension"
    assert run([quantity("x", 2, "m"), quantity("y", 3, "m")], [step]).valid


def test_formula_rejects_wrong_dimension_input() -> None:
    facts = [quantity("v", 20, "kg"), quantity("t", 3, "s")]
    step = Step("s1", "kinematics.distance.solve_d", {"v": "v", "t": "t"},
                {"d": quantity("d", 60, "m")})
    v = run(facts, [step])
    assert codes(v) == ["precondition_failed"] and "v=v has unit 'kg'" in v.failures[0].message


def test_formula_rejects_claimed_wrong_unit() -> None:
    facts = [quantity("v", 20, "m/s"), quantity("t", 3, "s")]
    step = Step("s1", "kinematics.distance.solve_d", {"v": "v", "t": "t"},
                {"d": quantity("d", 60, "s")})
    assert codes(run(facts, [step])) == ["output_mismatch"]


def test_formula_domain_and_ambiguity() -> None:
    neg_t = [quantity("v", 20, "m/s"), quantity("t", -3, "s")]
    step = Step("s1", "kinematics.distance.solve_d", {"v": "v", "t": "t"},
                {"d": quantity("d", -60, "m")})
    assert run(neg_t, [step]).failures[0].precondition == "domain"
    # solving s = u t + a t^2 / 2 for t has two real roots when both are >= 0
    facts = [quantity("s", 5, "m"), quantity("u", 6, "m/s"), quantity("a", -2, "m/s^2")]
    step = Step("s2", "kinematics.displacement.solve_t", {"s": "s", "u": "u", "a": "a"},
                {"t": quantity("t", 1, "s")})
    v = run(facts, [step])
    assert codes(v) == ["effect_error"] and "2 admissible solutions" in v.failures[0].message


def test_linear_solver_and_z3() -> None:
    eq = Fact("eq", "equation", value="2*y + 1 = 0")
    good = Step("s1", "algebra.solve_linear", {"equation": "eq"},
                {"solution": quantity("y", -0.5, "1", "y")})
    assert run([eq], [good]).valid
    for text in ["x^2 = 4", "x + y = 1", "3 = 3"]:
        v = run([Fact("eq", "equation", value=text)], [good])
        assert codes(v) == ["precondition_failed"], text


def test_z3_checker_independently_rejects_a_wrong_root() -> None:
    from openverifiers.domains.math import _z3_unique

    inputs = {"equation": Fact("eq", "equation", value="2*y + 1 = 0")}
    assert _z3_unique(inputs, {}, {"solution": quantity("y", -0.5, "1")}) is None
    wrong = _z3_unique(inputs, {}, {"solution": quantity("y", 3, "1")})
    assert wrong is not None and "unique solution is -1/2" in wrong


@pytest.mark.parametrize("payload", [
    "__import__('os').system('true')",
    "x.__class__ = 1",
    "open('f')",
    "x; y",
])
def test_equation_parser_refuses_code(payload: str) -> None:
    with pytest.raises((ValueError, SyntaxError, TypeError, NameError)):
        parse_side(payload)


def test_equation_symbols_are_plain_symbols() -> None:
    assert parse_side("E + I").free_symbols == {*parse_side("E").free_symbols,
                                                 *parse_side("I").free_symbols}


def test_grounded_constant_must_match_source() -> None:
    def lookup(value: float, cite: str) -> Step:
        g = quantity("g", value, "m/s^2", "g", provenance=Provenance("lookup", citation=cite))
        return Step("s0", "constant.lookup", {}, {"value": g})
    goal = [Requirement("r", Selector("g"))]
    assert run([], [lookup(9.80665, "codata:g_n")], goal).trust_grade == "grounded"
    assert codes(run([], [lookup(9.81, "codata:g_n")])) == ["checker_rejected"]
    assert codes(run([], [lookup(9.80665, "wikipedia")])) == ["checker_rejected"]


def test_division_by_zero_is_a_precondition() -> None:
    step = Step("s1", "arith.div", {"a": "x", "b": "y"}, {"result": quantity("z", 0, "m/s")})
    v = run([quantity("x", 1, "m"), quantity("y", 0, "s")], [step])
    assert v.failures[0].precondition == "nonzero_divisor"
