"""Condition B: mutation tests of the object path. Real records from real runs are
mutated, and the trusted checker (checker/objects.py) re-checks them. A mutant is
unsound if the checker accepts it while its claim is false. Truth is judged by an
independent oracle: for a model, the untrusted expander evaluates the class
invariants at the instance; for a theorem, its own verdict in the run (PROVEN is
true, REFUTED by a checked counterexample is false, UNKNOWN is not judged); a
moved uniqueness value, an unknown class and an unchecked lemma are false."""

from __future__ import annotations

import copy
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from openverifiers.checker.objects import check_records
from openverifiers.objects.engine import Settings
from openverifiers.objects.expand import FALSE, TRUE, Expander, and_
from openverifiers.raw.canon import term_from_json
from openverifiers.raw.formula import Unsupported
from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "src/openverifiers/packages/physics/mechanics.ov",
         ROOT / "src/openverifiers/packages/math/calculus.ov",
         ROOT / "src/openverifiers/packages/math/core.ov",
         ROOT / "tests/v1/transcendental.ov",
         ROOT / "benchmarks/exams/jee2025/jee2025-math-p1q7/case.ov",
         ROOT / "benchmarks/exams/jee2025/jee2025-phys-p2q9/case.ov",
         ROOT / "benchmarks/exams/jee2025/jee2025-phys-p2q12/case.ov",   # positive sums,
         ROOT / "benchmarks/exams/jee2025/jee2025-math-p2q12/case.ov"]   # surds (D-030)


def _records() -> list[tuple[list[dict[str, Any]], Any, int, dict[str, str]]]:
    """(the run's records in order, its class definitions, a record's index, the
    run's theorem verdicts)."""
    out = []
    for f in FILES:
        res = run_file(f, files={str(f)}, settings=Settings(drafts=True))
        recs = [r for a in (*res.classes, *res.objects) for r in a.records]
        assert not check_records(recs, res.env.objects.defs), f     # the originals pass
        verdicts = {a.title.removeprefix("theorem "): a.verdict for a in res.classes
                    if a.kind == "theorem"}
        out += [(recs, res.env.objects.defs, i, verdicts) for i in range(len(recs))]
    return out


def _truth(m: dict[str, Any], defs: Any, verdicts: dict[str, str]) -> bool | None:
    """Whether a mutant's claim is true, by the independent oracle (None: not judged)."""
    if m["class"] not in defs or set(m.get("lemmas", [])) - set(verdicts):
        return False
    if m["kind"] == "model":
        props = {k: term_from_json(v) for k, v in m["props"].items()}
        try:
            cf = and_([Expander(props).formula(f) for _, f in defs[m["class"]].invariants])
        except Unsupported:
            return None
        return None if cf not in (TRUE, FALSE) else cf == TRUE
    if "goal" in m:
        return False                    # only reached for the moved uniqueness value
    return {"PROVEN": True, "REFUTED": False}.get(verdicts.get(m["theorem"], ""))


def _bump(t: list[Any]) -> list[Any]:
    """A term with its first number changed by 1/7 (a different value)."""
    t = copy.deepcopy(t)
    stack = [t]
    while stack:
        x = stack.pop()
        if isinstance(x, list) and x and x[0] == "num":
            x[1] = str(Fraction(x[1]) + Fraction(1, 7))
            return t
        if isinstance(x, list):
            stack.extend(reversed(x))
    return t


def _mutants(r: dict[str, Any], defs: Any) -> list[tuple[str, dict[str, Any]]]:
    out = []
    if r["kind"] == "model":
        m = copy.deepcopy(r)
        for k in m["props"]:
            m["props"][k] = _bump(m["props"][k])
        out.append(("model: every value moved", m))
        out.append(("model: another class", {**r, "class": "NoSuchClass"}))
        return out
    c = r["cert"]
    if c["coeffs"]:
        m = copy.deepcopy(r)
        m["cert"]["coeffs"][0][1] = ["app", "*", [["num", "2", []], c["coeffs"][0][1]]]
        out.append(("certificate: a coefficient doubled", m))
        m = copy.deepcopy(r)
        m["cert"]["coeffs"] = []
        out.append(("certificate: ideal part dropped", m))
    if c["factors"] or c["constants"]:
        m = copy.deepcopy(r)
        m["cert"]["factors"], m["cert"]["constants"] = [], []
        out.append(("certificate: multiplier dropped", m))
    if c["squares"]:
        m = copy.deepcopy(r)
        m["cert"]["squares"][0][0] = str(-Fraction(m["cert"]["squares"][0][0]) - 1)
        out.append(("certificate: negative square weight", m))
    if c["induction"]:
        m = copy.deepcopy(r)
        m["cert"]["induction"] = list(reversed(c["induction"]))
        out.append(("certificate: induction hypotheses swapped", m))
    if c.get("sums"):
        m = copy.deepcopy(r)
        m["cert"]["sums"] = []
        out.append(("certificate: positive sum dropped", m))
        m = copy.deepcopy(r)
        k = m["cert"]["sums"][0][0][0]
        m["cert"]["sums"][0][0][0] = ["app", "*", [["num", "-1", []], k]]
        out.append(("certificate: positive sum constant negated", m))
    if "goal" in r:
        out.append(("uniqueness: goal value moved", {**r, "goal": _bump(r["goal"])}))
    if "theorem" in r:
        cls = defs[r["class"]]
        own = dict(cls.theorems)[r["theorem"]]
        for other, f in cls.theorems:            # claim a different theorem
            if f != own:
                out.append((f"certificate: claims {other}", {**r, "theorem": other}))
        out.append(("certificate: unchecked lemma", {**r, "lemmas": ["No.such"]}))
    return out


def test_no_unsound_mutant_is_accepted() -> None:
    tally: Counter[str] = Counter()
    unsound = []
    for recs, defs, i, verdicts in _records():
        for what, m in _mutants(recs[i], defs):
            mutated = [*recs[:i], m, *recs[i + 1:]]
            rejected = any(b.startswith(f"record {i} ") for b in check_records(mutated, defs))
            truth = _truth(m, defs, verdicts)
            tally[("rejected" if rejected else "accepted") + f" / claim {truth}"] += 1
            if not rejected and truth is False:
                unsound.append((what, recs[i].get("theorem") or recs[i]["class"]))
            if what.startswith("certificate: positive sum"):
                tally["positive-sum mutants"] += 1
                assert rejected, (what, recs[i]["class"])   # its multiplier is gone or < 0
    print(dict(tally))
    assert tally["rejected / claim False"] >= 50, tally
    assert unsound == [], unsound[:10]                 # 0 unsound mutants accepted
    assert tally["positive-sum mutants"] >= 4, tally
