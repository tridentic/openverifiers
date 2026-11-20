"""HSC q11 in hand-written RawOV: the reference answers (brief §3.6)."""

from __future__ import annotations

import time

from openverifiers.checker import Proven, Refuted
from openverifiers.engine import Run, ask, find_all, run, without
from openverifiers.raw import Atom, Str, Term, parse_atom

from .programs import q11


def name(r: Run, t: Term) -> str:
    for a in r.model.atoms():
        if a.pred == "name" and a.args[0] == t and isinstance(a.args[1], Str):
            return a.args[1].value
    return getattr(t, "name", repr(t))


def proven(r: Run, pattern: str) -> list[tuple[dict[str, str], Proven]]:
    return [({k: name(r, t) for k, t in s.items()}, v)
            for s, v in find_all(r, parse_atom(pattern)) if isinstance(v, Proven)]


def test_q11_reference_answers() -> None:
    start = time.perf_counter()
    r = run(q11())
    assert time.perf_counter() - start < 1.0
    assert all(r.trace.complete)

    # FIND ?A, ?C, ?D: unique, no assumptions
    [(acd, v1)] = proven(r, "value_acd(A, C, D)")
    assert acd == {"A": "2-methylbut-1-ene", "C": "butanone", "D": "methanal"}
    assert v1.assumptions == frozenset()

    # FIND ?p WHERE major(add(B, HBr, peroxide)) = ?p: 1-bromopentane under {single_major}
    [(p, v2)] = proven(r, "q2(P)")
    assert p == {"P": "1-bromopentane"}
    assert v2.assumptions == {("single_major", True)}
    # ... and it really depends on the assumption: without it, B is not determined
    assert not proven(run(without(q11(), {"single_major"})), "q2(P)")

    # PROVE optically_active(add(C, HCN)): REFUTED (stereocentre, but racemic)
    v3 = ask(r, Atom("q3"))
    assert isinstance(v3, Refuted) and not v3.closed_world and v3.assumptions == frozenset()
    used = {r.model.steps[i].rule_id for i in v3.proof}
    assert {"rac", "st1", "oa1"} <= used


def test_q11_what_if_retract_not_tautomerizes() -> None:
    r = run(without(q11(), {"f_taut"}))
    assert not proven(r, "value_a(A)")                      # FIND ?A -> UNKNOWN
    cands = sorted(s["A"] for s, _ in proven(r, "cand_acd(A, C, D)"))
    assert cands == ["2-methylbut-1-ene", "2-methylbut-2-ene"]  # two candidates
    u = ask(r, parse_atom("value_a('2-methylbut-1-ene')"))
    assert type(u).__name__ == "Unknown"


def test_q11_b_candidates_under_and_without_the_assumption() -> None:
    r = run(q11())
    b = {name(r, s["B"]): type(v).__name__ for s, v in find_all(r, parse_atom("cand_b(B)"))}
    assert b["pent-1-ene"] == "Proven"
    assert b["pent-2-ene"] == "Refuted"                      # only under single_major
    v = ask(r, parse_atom("cand_b('pent-2-ene')"), frozenset())
    assert isinstance(v, Proven) and v.assumptions == {("single_major", False)}
