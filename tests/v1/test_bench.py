"""`ov bench`: discovery, gold comparison, outputs (on a throwaway benchmarks dir)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from openverifiers.bench.run import compare, main

CASE = """package benchx.n2
import physics.mechanics

test n2 {{
  scenario {scn} uses physics.mechanics {{
    entity cart: Body
    fact net_force(cart, 12 N)
    fact cart.accel = 3 m/s^2
  }}
  query FIND ?m WHERE {scn}.cart.mass = ?m
}}
"""


def make(root: Path, suite: str, name: str, src: str, gold: dict[str, object]) -> None:
    d = root / suite / name
    d.mkdir(parents=True)
    (d / "case.ov").write_text(src)
    (d / "expected.json").write_text(json.dumps(gold))


def query(scn: str) -> str:
    return f"FIND ?m WHERE {scn}.cart.mass = ?m"


@pytest.fixture
def bench(tmp_path: Path) -> Path:
    root = tmp_path / "benchmarks"
    make(root, "physics", "right", CASE.format(scn="bx_right"), {
        "queries": [{"query": query("bx_right"), "verdict": "PROVEN", "values": ["4 kg"],
                     "assumptions": []}]})
    make(root, "physics", "wrong", CASE.format(scn="bx_wrong"), {
        "queries": [{"query": query("bx_wrong"), "verdict": "PROVEN", "values": ["5 kg"]}]})
    make(root, "adversarial", "unit_trap",
         CASE.format(scn="bx_unit").replace("12 N", "12 m"), {"error": ["E301"]})
    return root


def test_bench_compares_with_gold_and_writes_outputs(bench: Path, tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    assert main([str(bench), "--seeds", "2", "--out", str(out)]) == 1   # one case fails
    printed = capsys.readouterr().out
    assert "ok   physics/right" in printed and "ok   adversarial/unit_trap" in printed
    assert "FAIL physics/wrong" in printed and "q1 values: gold ['5 kg'], got ['4 kg']" in printed
    rows = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 6 and {r["seed"] for r in rows} == {0, 1}
    summary = {r["suite"]: r for r in csv.DictReader((out / "summary.csv").open())}
    assert summary["all"]["cases"] == "3" and summary["all"]["passed"] == "2"
    assert summary["all"]["false_proven"] == "0" and summary["all"]["seed_varied_cases"] == "0"
    assert "## Mismatches (seed 0)" in (out / "summary.md").read_text()


def test_gold_is_never_matched_to_a_different_query() -> None:
    gold = {"queries": [{"query": "FIND ?x", "verdict": "PROVEN"}]}
    got = {"queries": [{"query": "FIND ?y", "verdict": "PROVEN"}], "classes": []}
    [m] = compare(gold, got)
    assert "gold is for 'FIND ?x'" in m


def test_false_proven_is_counted(tmp_path: Path) -> None:
    root = tmp_path / "b"
    make(root, "physics", "c", CASE.format(scn="bx_fp"), {
        "queries": [{"query": query("bx_fp"), "verdict": "UNKNOWN"}]})
    out = tmp_path / "o"
    assert main([str(root), "--out", str(out)]) == 1
    [row] = [r for r in csv.DictReader((out / "summary.csv").open()) if r["suite"] == "all"]
    assert row["false_proven"] == "1" and row["unknown_recall"] == "0.0"


def test_bench_usage_errors(tmp_path: Path) -> None:
    assert main([str(tmp_path)]) == 2                    # no cases
    assert main(["--seeds"]) == 2
    assert main(["--frob"]) == 2


def test_values_compare_as_quantities() -> None:
    from openverifiers.bench.run import value_text
    assert value_text("500 g") == value_text("0.5 kg")
    assert value_text("4 m/s^2") == value_text("4 m/s^2")
    assert value_text("(3, 5)") == "(3, 5)" and value_text("2-chloropentane") == "2-chloropentane"
    assert value_text("5 kg") != value_text("5 g")


def test_kernel_rejections_and_crashes_are_outcomes(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from openverifiers.bench import run as bench_run
    from openverifiers.bench.run import Case, run_case
    from openverifiers.kernel.strata import NotStratifiable
    from openverifiers.objects.engine import Settings

    def boom(exc: Exception):  # type: ignore[no-untyped-def]
        def f(*a: object, **k: object) -> None:
            raise exc
        return f
    c = Case("adversarial", "x", tmp_path / "case.ov", {"error": ["not_stratifiable"]})
    monkeypatch.setattr(bench_run, "run_file", boom(NotStratifiable(["p", "p"], "r1")))
    assert run_case(c, 0, Settings())["pass"]
    monkeypatch.setattr(bench_run, "run_file", boom(KeyError("k")))
    r = run_case(c, 0, Settings())
    assert not r["pass"] and r["outcome"]["error"] == ["crash:KeyError"]


# Cases whose gold OV does not meet yet (step-2 report, 2026-11-21). Each is a
# missing capability, not a wrong definite verdict. Fixing one means removing it
# here; the gold is never edited to match.
KNOWN_MISMATCHES = {
    "mathematics/linear_system",     # no linear-system solving yet (M5)
    "physics/push_block",            # FIND reports no missing facts (open_world)
}


def test_benchmark_suites_against_gold(tmp_path: Path) -> None:
    """Golden test over benchmarks/: no crash, no false PROVEN or REFUTED, and the
    failing set never grows."""
    root = Path(__file__).resolve().parents[2] / "benchmarks"
    main([str(root), "--out", str(tmp_path)])
    rows = [json.loads(x) for x in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert len(rows) >= 36
    assert not [r for r in rows if any(e.startswith("crash:")
                                       for e in r["outcome"].get("error", []))]
    [total] = [r for r in csv.DictReader((tmp_path / "summary.csv").open())
               if r["suite"] == "all"]
    assert total["false_proven"] == "0" and total["false_refuted"] == "0"
    failing = {f"{r['suite']}/{r['case']}" for r in rows if not r["pass"]}
    assert failing <= KNOWN_MISMATCHES, failing - KNOWN_MISMATCHES
