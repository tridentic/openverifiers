"""Gap (e): symbolic sums proven by induction, in three domains, and the checker's
refusals."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from openverifiers.raw.certificate import Certificate, check
from openverifiers.raw.formula import holds
from openverifiers.raw.terms import Compound, Num, Str, Term
from openverifiers.runner import run_file

TEXT = """package probe.sums
# mathematics: Gauss and the sum of squares
fact type Naturals {
  property n: Integer
  invariant natural: n >= 0
  theorem gauss: sum(i, i, n) = n * (n + 1) / 2
  theorem squares: sum(i * i, i, n) = n * (n + 1) * (2 * n + 1) / 6
  theorem cubes: sum(i * i * i, i, n) = (n * (n + 1) / 2) * (n * (n + 1) / 2)
  theorem off_by_one: sum(i, i, n) = n * n / 2
}
# physics: from rest under constant acceleration, the distances covered in
# successive equal intervals go as 1 : 3 : 5 : ... (Galileo); n intervals cover n^2
# units, matching s = a t^2 / 2
fact type Galileo {
  property n: Integer
  invariant natural: n >= 0
  theorem odd_numbers: sum(2 * k - 1, k, n) = n * n
}
# chemistry: shell k holds at most 2 k^2 electrons; shells 1..n hold at most
# n (n + 1) (2 n + 1) / 3
fact type Shells {
  property n: Integer
  invariant natural: n >= 0
  theorem capacity: sum(2 * k * k, k, n) = n * (n + 1) * (2 * n + 1) / 3
}
scenario s uses probe.sums {
  query COUNTEREXAMPLE Naturals.off_by_one
}
"""


def test_sums_by_induction_in_three_domains(tmp_path: Path) -> None:
    f = tmp_path / "s.ov"
    f.write_text(TEXT)
    res = run_file(f, files={str(f)})
    th = {a.title.removeprefix("theorem "): a for a in res.classes if a.kind == "theorem"}
    for name in ("Naturals.gauss", "Naturals.squares", "Naturals.cubes", "Galileo.odd_numbers",
                 "Shells.capacity"):
        assert th[name].verdict == "PROVEN" and th[name].trust_base == {"kernel"}, name
        assert any("induction" in s for s in th[name].steps)
    assert th["Naturals.off_by_one"].verdict == "REFUTED"
    assert res.objects[0].verdict == "REFUTED"                        # the query too


def p(x: str) -> Compound:
    return Compound("f.p", (Str(x),))


def test_the_checker_refuses_unsound_inductions() -> None:
    n, i = p("n"), Compound("f.v", (Str("i"),))
    hyps: dict[str, Term] = {"int": Compound("f.isint", (n,)),
                             "nat": Compound("f.cmp", (Str(">="), n, Num(Fraction(0)))),
                             "real": Compound("f.cmp", (Str(">="), n, Num(Fraction(1))))}

    def goal(body: Term, rhs: Term) -> Compound:
        return Compound("f.cmp", (Str("="), Compound("f.sum", (body, Str("i"), n)), rhs))
    gauss = goal(i, Compound("/", (Compound("*", (n, Compound("+", (n, Num(Fraction(1)))))),
                                   Num(Fraction(2)))))
    assert check(gauss, hyps, Certificate(induction=("int", "nat")))
    assert not check(gauss, hyps, Certificate(induction=("int", "real")))   # wrong base
    assert not check(gauss, {"nat": hyps["nat"]}, Certificate(induction=("int", "nat")))
    assert not check(goal(n, Compound("*", (n, n))), hyps,                   # body mentions n
                     Certificate(induction=("int", "nat")))
    assert not check(goal(i, n), hyps, Certificate(induction=("int", "nat")))  # false
    # The evaluator sums concretely: 1 + 4 + 9 + 16 = 30.
    assert holds(Compound("f.cmp", (Str("="), Compound("f.sum", (
        Compound("*", (i, i)), Str("i"), n)), Num(Fraction(30)))), {"n": Num(Fraction(4))})
