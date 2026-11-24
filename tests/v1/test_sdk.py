"""The Python SDK (v1 scope): its stable surface, and each call on real files."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from openverifiers import sdk

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "drafts/policies/repo_policy.ov"


def test_the_public_surface_is_stable() -> None:
    """Within v1 the public names and result fields only grow (docs/SDK.md)."""
    assert sdk.SDK_VERSION == "1.0"
    assert set(sdk.__all__) >= {"SDK_VERSION", "ClassCheck", "Diagnostic", "OVError",
                                "QueryResult", "Report", "blueprints", "check",
                                "check_source", "export_state", "gate_files",
                                "gate_tool_call"}
    assert all(hasattr(sdk, n) for n in sdk.__all__)
    fields = {f for f in sdk.QueryResult.__dataclass_fields__}
    assert fields >= {"query", "line", "verdict", "trust", "values", "assumptions", "reason",
                      "missing"}
    assert set(sdk.Report.__dataclass_fields__) >= {"file", "queries", "classes",
                                                     "provisional", "failed_expectations"}


def test_check_a_file() -> None:
    r = sdk.check(ROOT / "examples/chem/q11.ov")
    assert r.ok and r.provisional == ()
    got = [(q.verdict, q.values, q.trust) for q in r.queries]
    assert got[0] == ("PROVEN", ("2-methylbut-1-ene, butanone, methanal",), ("kernel",))
    assert r.queries[1].assumptions == ("single_major",)
    assert r.queries[3].verdict == "UNKNOWN" and not r.queries[3].kernel_checked
    js = json.loads(json.dumps(r.to_json()))              # plain JSON
    assert js["ok"] is True and js["queries"][2]["verdict"] == "REFUTED"


def test_check_source_and_errors() -> None:
    src = ("package demo\ntype Thing\npredicate checked(x: Thing) world closed\n"
           "scenario s uses demo {\n  entity a, b: Thing\n  fact checked(a)\n"
           "  query PROVE checked(a)\n  query PROVE checked(b)\n}\n")
    r = sdk.check_source(src, name="demo.ov")
    assert [q.verdict for q in r.queries] == ["PROVEN", "REFUTED"]
    assert all(q.kernel_checked for q in r.queries)
    with pytest.raises(sdk.OVError) as e:
        sdk.check_source("package broken\nfact q(z)\n", name="broken.ov")
    assert e.value.diagnostics


def test_strict_refuses_solver_only_verdicts() -> None:
    case = ROOT / "benchmarks/exams/jee2025/jee2025-math-p1q10/case.ov"
    default, strict = sdk.check(case), sdk.check(case, strict=True)
    [d], [st] = default.queries, strict.queries          # COUNT rests on a z3 unsat
    assert (d.verdict, d.trust, d.kernel_checked) == ("PROVEN", ("kernel", "z3_unsat"), False)
    assert (st.verdict, st.trust) == ("UNKNOWN", ())


def test_gates_state_and_blueprints(tmp_path: Path) -> None:
    decide = {t: sdk.gate_tool_call(POLICY, *t, drafts=True)["decision"]
              for t in (("run_tests", "feature"), ("push", "main"), ("deploy", "prod"),
                        ("format", "disk"))}
    assert decide == {("run_tests", "feature"): "permitted", ("push", "main"): "refused",
                      ("deploy", "prod"): "needs_human", ("format", "disk"): "needs_human"}
    [(_path, ok, line)] = sdk.gate_files([ROOT / "src/openverifiers/packages/math/core.ov"])
    assert ok and "ok" in line
    fam = tmp_path / "fam.ov"
    fam.write_text("package fam\ntype P\npredicate parent(a: P, b: P) world closed\n"
                   "scenario s uses fam {\n  entity ann, bob: P\n  fact parent(ann, bob)\n}\n")
    st = sdk.export_state(fam)
    assert set(st) == {"sha256", "body"} and len(st["sha256"]) == 64  # type: ignore[arg-type]
    bp = sdk.blueprints(ROOT / "src/openverifiers/packages/physics/mechanics.ov")
    assert bp and {"theorem", "statement", "closure", "steps"} <= set(bp[0])


def test_the_quickstart_runs(capsys: pytest.CaptureFixture[str],
                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    runpy.run_path(str(ROOT / "examples/sdk/quickstart.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "push main: refused" in out and "run_tests feature: permitted" in out
