"""D-027: integers and modular arithmetic, in three domains."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.raw.formula import Unsupported, holds
from openverifiers.raw.terms import Compound, Num, Str
from openverifiers.runner import run_file


def _run(tmp_path: Path, text: str) -> object:
    f = tmp_path / "i.ov"
    f.write_text(text)
    return run_file(f, files={str(f)})


def test_mathematics_remainders(tmp_path: Path) -> None:
    res = _run(tmp_path, """package probe.m
fact type Div {
  property n: Integer
  property r: Integer
  invariant range: n >= 1 n <= 30
  invariant rem: r = mod(n, 7)
  theorem small: r < 7
}
scenario s uses probe.m {
  query COUNT ?n WHERE Div{ n = ?n, r = 3 }
  query FIND ?r WHERE Div{ n = 23, r = ?r }
  query FIND ?n WHERE Div{ n = ?n, r = 9 }
}
""")
    count, find, none = res.objects                                  # type: ignore[attr-defined]
    assert count.count == 4 and find.bindings[0]["r"] == Num(Fraction(2))
    assert none.verdict == "REFUTED"                                  # no remainder 9 mod 7


def test_physics_bohr_orbits_are_whole_numbers(tmp_path: Path) -> None:
    res = _run(tmp_path, """package probe.p
fact type Orbit {
  property n: Integer
  property Z: Integer
  property r: Real
  invariant whole: n >= 1 Z >= 1
  invariant radius: r * Z = n * n
}
scenario s uses probe.p {
  query PROVE UNIQUE ?n WHERE Orbit{ Z = 1, r = 9, n = ?n }
  query FIND ?n WHERE Orbit{ Z = 1, r = 2, n = ?n }
}
""")
    nine, two = res.objects                                           # type: ignore[attr-defined]
    assert nine.verdict == "PROVEN" and nine.bindings[0]["n"] == Num(Fraction(3))
    assert two.verdict == "REFUTED"                                   # sqrt 2 is no orbit


def test_chemistry_balancing_with_whole_coefficients(tmp_path: Path) -> None:
    res = _run(tmp_path, """package probe.c
# a C3H8 + b O2 -> c CO2 + d H2O, with whole positive coefficients.
fact type Propane {
  property a: Integer
  property b: Integer
  property c: Integer
  property d: Integer
  invariant positive: a >= 1 b >= 1 c >= 1 d >= 1
  invariant carbon: 3 * a = c
  invariant hydrogen: 8 * a = 2 * d
  invariant oxygen: 2 * b = 2 * c + d
}
scenario s uses probe.c {
  query FIND ?b, ?c, ?d WHERE Propane{ a = 1, b = ?b, c = ?c, d = ?d }
  query FIND ?a WHERE Propane{ a = ?a, b = 1 }
}
""")
    one, frac = res.objects                                           # type: ignore[attr-defined]
    assert one.verdict == "PROVEN" and one.bindings[0]["b"] == Num(Fraction(5))
    assert frac.verdict == "REFUTED"                                  # b = 1 needs a = 1/5


def test_trusted_integer_checks() -> None:
    n = Compound("f.p", (Str("n"),))
    isint = Compound("f.isint", (n,))
    assert holds(isint, {"n": Num(Fraction(4))})
    assert not holds(isint, {"n": Num(Fraction(7, 2))})
    assert not holds(isint, {"n": Compound("f.surd", (Num(Fraction(2)), Num(Fraction(1))))})
    mod = Compound("f.cmp", (Str("="), Compound("f.mod", (Num(Fraction(-7)), Num(Fraction(3)))),
                             Num(Fraction(2))))
    assert holds(mod, {})                                             # floor convention
    with pytest.raises(Unsupported):
        holds(Compound("f.cmp", (Str("="), Compound("f.mod", (Num(Fraction(1)),
                                                              Num(Fraction(0)))),
                                 Num(Fraction(0)))), {})
