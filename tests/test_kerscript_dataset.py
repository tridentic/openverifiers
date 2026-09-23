"""KDScript acceptance gate — THE dataset.

Every entry in datasets/kerscript/*.json is a must-pass target: given facts
+ a KDScript-Proof trace, run against the COMPILED opk grammars (not the
Python grammars). A failing or wrong-valued entry here is a failing v1.

This test is the definition of "KDScript v1 works". No render-only checks;
every assertion is an executed proof.
"""
import json
from pathlib import Path

import pytest

from openverifiers.facts import Quantity, ActionFact, EnumValue
from openverifiers.v2 import Registry, parse_dsl, run_trace
from openverifiers.kerscript.compiler import load_grammar
from openverifiers.kerscript.units import resolve_token

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "datasets" / "kerscript"

_GRAMMAR_NAMES = ("math", "logic", "law", "business", "english", "physics")
_REGISTRY = Registry([load_grammar(ROOT / f"opk/{n}.opk")
                      for n in _GRAMMAR_NAMES])


def _facts(entries: list[dict]) -> list[dict]:
    out = []
    for e in entries:
        out.append({"id": e["id"], "domain": e["domain"],
                    "topics": e["topics"], "difficulty": e["difficulty"],
                    "entry": e})
    return out


def _load_all():
    entries = []
    meta = json.loads((DS / "index.json").read_text())
    for fname in meta["files"]:
        for e in json.loads((DS / fname).read_text()):
            e["file"] = fname
            entries.append(e)
    return entries

ALL_ENTRIES = _load_all()
PARAMS = _facts(ALL_ENTRIES)
IDS = [e["id"] for e in ALL_ENTRIES]


def _given_fact(bid: str, rec: dict):
    if rec["kind"] == "quantity":
        return Quantity(id=bid, value=rec["value"],
                        unit=resolve_token(rec["unit"]))
    value = rec["value"]
    if isinstance(value, bool):
        return ActionFact(id=bid, kind=rec["kind_name"], value=value,
                          of=rec.get("of"))
    return ActionFact(id=bid, kind=rec["kind_name"],
                      value=EnumValue(enum="given", value=str(value)),
                      of=rec.get("of"))


def _check(entry: dict) -> dict:
    given = {bid: _given_fact(bid, rec)
             for bid, rec in entry.get("given", {}).items()}
    r = run_trace(_REGISTRY, _REGISTRY.facts | given,
                  parse_dsl(entry["proof"]))
    return {"verdict": r.verdict, "reason": r.reason, "env": r.env}


@pytest.mark.parametrize("entry", ALL_ENTRIES, ids=IDS)
def test_dataset_entry(entry):
    got = _check(entry)
    must_fail = entry.get("must_fail", False)
    if must_fail:
        assert got["verdict"] != "pass", (
            f"{entry['id']}: expected failure, trace passed "
            f"({got['reason']})")
        return
    assert got["verdict"] == "pass", (
        f"{entry['id']}: trace failed — {got['reason']}")
    exp = entry.get("expected") or {}
    if exp.get("value") is None:
        return                      # structural fact (forall/impl/negation)
    fact = got["env"].get(exp["id"])
    assert fact is not None, f"{entry['id']}: expected fact {exp['id']} missing"
    exp_v = exp["value"]
    if isinstance(exp_v, str):
        val = getattr(fact, "value", None)
        assert getattr(val, "value", val) == exp_v, (
            f"{entry['id']}: {exp['id']} = {val!r}, expected {exp_v!r}")
    else:
        num = getattr(fact, "value", None)
        assert num is not None, f"{entry['id']}: {exp['id']} has no value"
        scale = max(1.0, abs(exp_v))
        assert abs(float(num) - exp_v) <= 1e-6 * scale, (
            f"{entry['id']}: {exp['id']} = {num}, expected {exp_v}")


def test_dataset_covers_all_five_domains():
    domains = {e["domain"] for e in ALL_ENTRIES}
    assert {"physics", "math", "logic", "law", "business", "english"} \
        <= domains


def test_every_english_verdict_is_judged_tier():
    for e in ALL_ENTRIES:
        if e["domain"] != "english":
            continue
        got = _check(e)
        fact = got["env"].get(e["expected"]["id"])
        assert fact is not None and fact.provenance == "judged", (
            f"{e['id']}: judged step must land on the judged tier")


def test_all_physics_givens_are_unit_typed():
    for e in ALL_ENTRIES:
        if e["domain"] != "physics":
            continue
        for bid, rec in e.get("given", {}).items():
            if rec["kind"] == "quantity":
                assert rec.get("unit"), (
                    f"{e['id']}: given {bid} lacks a unit — the typed core "
                    f"requires one")