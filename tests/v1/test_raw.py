"""RawOV: canonical text round-trip, parse errors, builtins, labels."""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from openverifiers.raw import (
    Compound,
    Num,
    RawSyntaxError,
    Str,
    Sym,
    Var,
    dump,
    dump_term,
    make_dims,
    parse,
    parse_term,
    validate,
)
from openverifiers.raw import labels as L
from openverifiers.raw.builtins import compare, evaluate
from openverifiers.raw.terms import order_key

from .programs import PENGUIN, REACH, programs, q11

# ---------------------------------------------------------------- text


@pytest.mark.parametrize("prog", [REACH, PENGUIN], ids=["reach", "penguin"])
def test_roundtrip_examples(prog: object) -> None:
    assert parse(dump(prog)) == prog  # type: ignore[arg-type]


def test_roundtrip_q11() -> None:
    p = q11()
    assert parse(dump(p)) == p
    assert validate(p) == []


@settings(max_examples=150, deadline=None)
@given(programs())
def test_roundtrip_random_programs(prog: object) -> None:
    assert parse(dump(prog)) == prog  # type: ignore[arg-type]


names = st.sampled_from(["a", "x1", "Body", "2-chloro", "it's", "not", "neg", "+"])
fracs = st.fractions(max_denominator=50).filter(lambda f: abs(f) < 10**6)
dims = st.dictionaries(st.sampled_from(["m", "kg", "s", "A", "USD"]),
                       st.integers(-3, 3).map(Fraction), max_size=3).map(make_dims)
leaf = st.one_of(names.map(Sym), st.text(max_size=5).map(Str),
                 st.builds(Num, fracs, dims), st.sampled_from(["X", "Y", "_Z"]).map(Var))
terms = st.recursive(leaf, lambda kids: st.one_of(
    st.builds(Compound, names, st.lists(kids, min_size=1, max_size=3).map(tuple)),
    st.builds(lambda op, a, b: Compound(op, (a, b)), st.sampled_from("+-*/^"), kids, kids),
    st.builds(lambda a: Compound("-", (a,)), kids)), max_leaves=8)


@settings(max_examples=300, deadline=None)
@given(terms)
def test_term_roundtrip(t: object) -> None:
    assert parse_term(dump_term(t)) == t  # type: ignore[arg-type]


def test_negative_numbers_and_subtraction() -> None:
    assert parse_term("X - 3") == Compound("-", (Var("X"), Num(Fraction(3))))
    assert parse_term("f(-3/2{m^1,s^-2})") == Compound(
        "f", (Num(Fraction(-3, 2), make_dims({"m": 1, "s": -2})),))
    assert parse_term("0.25") == Num(Fraction(1, 4))


@pytest.mark.parametrize("src, line, col", [
    ("fact f1: p(a) .", 1, 15),               # missing origin
    ("rule r1: p(X) :- q(X)", 1, 22),         # missing '.'
    ("world p maybe.", 1, 9),
    ("fact f: p(a) @\"fact:t\".\nrule r: p(X) :- $.", 2, 17),
])
def test_parse_errors_have_positions(src: str, line: int, col: int) -> None:
    with pytest.raises(RawSyntaxError) as e:
        parse(src)
    assert (e.value.line, e.value.col) == (line, col)


def test_validate_catches_unsafe_rules() -> None:
    p = parse("rule r1: p(X) :- not q(X).\nrule r2: p(Y) :- q(X).\n"
              "rule r3: p(X) :- q(X), Y > 2.\nfact f: q(X) @\"fact:t\".\nfact f: q(a) @\"fact:t\".")
    errs = validate(p)
    assert any("r1" in e and "unbound" in e for e in errs)
    assert any("r2" in e and "head variable" in e for e in errs)
    assert any("r3" in e and "unbound" in e for e in errs)
    assert any("not ground" in e for e in errs)
    assert any("duplicate id 'f'" in e for e in errs)


# ---------------------------------------------------------------- builtins

def q(v: str, **d: int) -> Num:
    return Num(Fraction(v), make_dims(d))


def test_unit_arithmetic_is_exact_and_dimensioned() -> None:
    s = {"F": q("10", kg=1, m=1, s=-2), "A": q("2", m=1, s=-2)}
    assert evaluate(parse_term("F / A"), s) == q("5", kg=1)
    assert evaluate(parse_term("F + A"), s) is None             # kg*m/s^2 + m/s^2
    assert evaluate(parse_term("A ^ 2"), s) == q("4", m=2, s=-4)
    assert evaluate(parse_term("A / 0"), s) is None
    assert evaluate(parse_term("1/3 + 1/6"), {}) == q("1/2")
    assert compare("<", parse_term("A"), parse_term("3{m^1,s^-2}"), s)
    assert not compare("<", parse_term("A"), parse_term("3"), s)  # dimension mismatch


def test_sort_args_and_order() -> None:
    t = evaluate(parse_term("sort_args(c(c(h, h, h), h, c(h, h, c(h, h, h))))"), {})
    assert t == parse_term("c(h, c(h, h, h), c(h, h, c(h, h, h)))")
    assert order_key(Sym("h")) < order_key(parse_term("c(h, h, h)"))


# ---------------------------------------------------------------- labels

lits = st.tuples(st.sampled_from("abc"), st.booleans())
envs = st.frozensets(lits, max_size=3)
labels = st.lists(envs, max_size=4).map(L.minimize)
CONTEXTS = [frozenset(c) for n in range(4) for c in itertools.combinations("abc", n)]


@given(labels)
def test_negate_is_exact_complement(lab: L.Label) -> None:
    neg = L.negate(lab)
    for c in CONTEXTS:
        assert L.holds(neg, c) == (not L.holds(lab, c))


@given(labels, labels)
def test_conjoin_and_disjoin_semantics(a: L.Label, b: L.Label) -> None:
    for c in CONTEXTS:
        assert L.holds(L.conjoin(a, b), c) == (L.holds(a, c) and L.holds(b, c))
        assert L.holds(L.disjoin(a, b), c) == (L.holds(a, c) or L.holds(b, c))


@given(st.lists(envs, max_size=6))
def test_minimize_is_an_antichain_preserving_meaning(es: list[L.Env]) -> None:
    m = L.minimize(es)
    assert all(not (x < y) for x in m for y in m)
    assert all(L.consistent(e) for e in m)
    assert L.minimize(m) == m
    for c in CONTEXTS:
        assert L.holds(m, c) == any(L.satisfied(e, c) for e in es if L.consistent(e))
