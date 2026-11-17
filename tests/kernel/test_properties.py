"""Property tests: order invariance, determinism, purity, JSON round-trip."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from openverifiers.kernel import (
    FormatError,
    Proof,
    Requirement,
    Selector,
    Step,
    check,
    fact_from_dict,
    fact_to_dict,
    proof_from_dict,
    proof_to_dict,
    requirement_from_dict,
    verdict_to_dict,
)

from .toy_pack import PACK, num

KERNEL = Path(__file__).resolve().parents[2] / "openverifiers" / "kernel"


@st.composite
def add_chains(draw: st.DrawFn) -> tuple[list[Step], int]:
    """A random DAG of add steps over two seeds, all claims correct."""
    values = {"a": 2, "b": 3}
    steps: list[Step] = []
    for i in range(draw(st.integers(1, 8))):
        x, y = draw(st.sampled_from(sorted(values))), draw(st.sampled_from(sorted(values)))
        out = f"f{i}"
        values[out] = values[x] + values[y]
        steps.append(Step(f"s{i}", "add", {"a": x, "b": y}, {"sum": num(out, values[out])}))
    return steps, values[f"f{len(steps) - 1}"]


@given(add_chains(), st.randoms(use_true_random=False))
@settings(max_examples=60, deadline=None)
def test_correct_proofs_accepted_in_any_order(chain: tuple[list[Step], int], rnd: object) -> None:
    steps, final = chain
    shuffled = list(steps)
    rnd.shuffle(shuffled)  # type: ignore[attr-defined]
    last = steps[-1].outputs["sum"].id
    r = [Requirement("goal", Selector(last), "equals", {"value": final})]
    v = check([num("a", 2), num("b", 3)], r, Proof(tuple(shuffled)), PACK)
    assert v.valid, v.failures


@given(add_chains(), st.integers(0, 7), st.integers(1, 5))
@settings(max_examples=60, deadline=None)
def test_any_wrong_claim_is_rejected(chain: tuple[list[Step], int], idx: int, delta: int) -> None:
    steps, _ = chain
    i = idx % len(steps)
    bad = steps[i].outputs["sum"]
    steps[i] = Step(steps[i].id, "add", steps[i].inputs,
                    {"sum": num(bad.id, bad.value + delta)})
    v = check([num("a", 2), num("b", 3)], [], Proof(tuple(steps)), PACK)
    assert not v.valid
    assert v.failures[0].code == "output_mismatch" and v.failures[0].step_id == f"s{i}"


def test_check_is_deterministic() -> None:
    steps = (Step("s1", "add", {"a": "a", "b": "b"}, {"sum": num("c", 6)}),)
    one = verdict_to_dict(check([num("a", 2), num("b", 3)], [], Proof(steps), PACK))
    two = verdict_to_dict(check([num("a", 2), num("b", 3)], [], Proof(steps), PACK))
    assert json.dumps(one) == json.dumps(two)


def test_kernel_imports_only_the_standard_library() -> None:
    allowed = set(sys.stdlib_module_names) | {"__future__"}
    for path in KERNEL.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                assert root in allowed, f"{path.name} imports {name}"
                assert root not in {"socket", "urllib", "http", "subprocess"}, path.name


def test_trace_filters() -> None:
    steps = (Step("s1", "add", {"a": "a", "b": "b"}, {"sum": num("c", 5)}),
             Step("s2", "add", {"a": "a", "b": "a"}, {"sum": num("d", 5)}))
    v = check([num("a", 2), num("b", 3)], [Requirement("r", Selector("c"))], Proof(steps), PACK)
    full = verdict_to_dict(v, "full")["trace"]
    fail = verdict_to_dict(v, "failure_trail")["trace"]
    ok = verdict_to_dict(v, "success_path")["trace"]
    assert [e["subject"] for e in fail] == ["s2"]
    assert [e["subject"] for e in ok] == ["s1", "r"]
    assert len(full) == 4  # structure, s1, s2, r
    assert fail[0]["failures"][0]["code"] == "output_mismatch"
    with pytest.raises(ValueError):
        verdict_to_dict(v, "everything")  # type: ignore[arg-type]


def test_json_round_trip() -> None:
    raw = {"id": "x", "type": "num", "value": 1.5, "unit": "m", "status": "unverified",
           "attributes": {"symbol": "d"}, "children": [{"id": "k", "type": "num", "value": 1}],
           "provenance": {"source": "doc", "citation": "p1"}}
    assert fact_to_dict(fact_from_dict(raw)) == raw
    proof = {"steps": [{"id": "s1", "transformation": "add", "inputs": {"a": "a", "b": "b"},
                        "outputs": {"sum": {"id": "c", "type": "num", "value": 5}}}]}
    assert proof_to_dict(proof_from_dict(proof)) == proof


@pytest.mark.parametrize("bad", [
    {"id": "x"},
    {"id": "x", "type": "num", "colour": "red"},
    {"id": "", "type": "num"},
    {"id": "x", "type": "num", "status": "probably"},
    {"id": "x", "type": "num", "children": {}},
])
def test_fact_parsing_is_strict(bad: dict[str, object]) -> None:
    with pytest.raises(FormatError):
        fact_from_dict(bad)


def test_requirement_needs_exactly_one_selector() -> None:
    assert requirement_from_dict({"id": "r", "fact_id": "x"}).selector.fact_id == "x"
    with pytest.raises(FormatError):
        requirement_from_dict({"id": "r", "fact_id": "x", "where": {"a": 1}})
    with pytest.raises(FormatError):
        requirement_from_dict({"id": "r"})
