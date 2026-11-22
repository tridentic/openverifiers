"""The checker: accepts honest traces, rejects every corrupted one, stays small and isolated."""

from __future__ import annotations

import ast
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings

from openverifiers.checker import TraceRejected, Unknown, check_trace, verdict
from openverifiers.kernel import Budget, evaluate
from openverifiers.raw import Program
from openverifiers.raw import trace as T
from openverifiers.rawtext import parse

from .mutations import mutants
from .programs import NAT_SRC, PENGUIN, REACH, ROOT, programs, q11


def lowered(path: str) -> Program:
    """A RawOV program lowered from an .ov file (so lowered code is mutation-tested too)."""
    from openverifiers.lang.check import load
    from openverifiers.lower.lower import lower
    return lower(load(ROOT / path))[0].program


CORPUS = {"reach": REACH, "penguin": PENGUIN, "q11": q11(), "nat": parse(NAT_SRC),
          "q11_ov": lowered("examples/chem/q11.ov"),
          "newton2_ov": lowered("examples/physics/newton2.ov")}


def model_of(program: Program, trace: T.Trace) -> dict[object, object]:
    m = check_trace(program, trace)
    return {a: m.label(a) for a in m.atoms()}


def contexts(program: Program) -> list[frozenset[str]]:
    names = sorted(program.assumptions())
    return [frozenset(n for k, n in enumerate(names) if mask >> k & 1)
            for mask in range(2 ** len(names))]


def classify(program: Program, original: T.Trace, mutant: T.Trace) -> str:
    """killed | equivalent | weakened (accepted, every verdict the same or UNKNOWN) | survivor."""
    try:
        mm = check_trace(program, mutant)
    except TraceRejected:
        return "killed"
    om = check_trace(program, original)
    if {a: mm.label(a) for a in mm.atoms()} == {a: om.label(a) for a in om.atoms()} \
            and mm.complete == om.complete:
        return "equivalent"
    atoms = set(om.atoms()) | set(mm.atoms())
    for c in contexts(program):
        for a in atoms:
            got, want = verdict(mm, a, c), verdict(om, a, c)
            if type(got) is not type(want) and not isinstance(got, Unknown):
                return "survivor"
    return "weakened"


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_honest_traces_are_accepted_and_survive_json(name: str) -> None:
    p = CORPUS[name]
    tr = evaluate(p, Budget(max_depth=4) if name == "nat" else None)
    check_trace(p, tr)
    again = T.loads(T.dumps(tr))
    assert again == tr
    check_trace(p, again)


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_checker_kills_every_trace_mutant(name: str) -> None:
    p = CORPUS[name]
    tr = evaluate(p, Budget(max_depth=4) if name == "nat" else None)
    counts: dict[str, Counter[str]] = {k: Counter() for k in
                                       ("killed", "equivalent", "weakened", "survivor")}
    for op, mutant in mutants(tr, seed=1):
        counts[classify(p, tr, mutant)][op] += 1
    killed, survivors = sum(counts["killed"].values()), sum(counts["survivor"].values())
    total = killed + survivors + sum(counts["weakened"].values())
    print(f"\n{name}: killed {killed}/{total} non-equivalent mutants; "
          f"weakened-but-sound {dict(counts['weakened'])}; equivalent "
          f"{dict(counts['equivalent'])}; survivors {dict(counts['survivor'])}")
    assert survivors == 0, f"checker accepted unsound traces: {counts['survivor']}"
    for op, n in counts["weakened"].items():
        assert op == "dropped_step", (op, n)   # only removal can weaken soundly
    assert total > 0


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
@given(programs())
def test_checker_kills_mutants_of_random_programs(p: Program) -> None:
    tr = evaluate(p)
    for op, mutant in mutants(tr, seed=2):
        assert classify(p, tr, mutant) != "survivor", op


def test_claiming_completeness_after_a_budget_cut_is_rejected() -> None:
    p = parse(NAT_SRC)
    tr = evaluate(p, Budget(max_depth=3))
    assert tr.complete == (False,)
    with pytest.raises(TraceRejected, match="closure"):
        check_trace(p, replace(tr, complete=(True,)))


def test_negation_over_an_atom_the_trace_hides_is_rejected() -> None:
    tr = evaluate(REACH)
    # drop the h-dependent reach(a, d) and every step after it that mentions it
    hidden = [s.id for s in tr.steps if str(s.conclusion.args) .count("'d'") and
              s.conclusion.pred == "reach"]
    assert hidden
    with pytest.raises(TraceRejected):
        steps = tuple(s for s in tr.steps if s.id < hidden[0])
        check_trace(REACH, replace(tr, steps=steps))


def test_checker_does_not_import_untrusted_modules() -> None:
    forbidden = {"kernel", "prover", "okql", "engine", "plugins", "lang", "lower"}
    for f in (ROOT / "src" / "openverifiers" / "checker").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.ImportFrom):
                parts = (node.module or "").split(".")
                assert not forbidden & set(parts), f"{f.name} imports {node.module}"
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert not forbidden & set(n.name.split(".")), f"{f.name} imports {n.name}"


def test_trusted_modules_use_only_stdlib_and_raw() -> None:
    allowed = {"__future__", "collections", "dataclasses", "fractions", "json", "math", "re",
               "itertools", "functools", "typing", "hashlib"}
    for d in ("raw", "checker"):
        for f in (ROOT / "src" / "openverifiers" / d).rglob("*.py"):
            for node in ast.walk(ast.parse(f.read_text())):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    assert (node.module or "").split(".")[0] in allowed, (f, node.module)
                if isinstance(node, ast.Import):
                    assert all(n.name.split(".")[0] in allowed for n in node.names), f


def test_trusted_code_size_gate() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "tcb_size.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout


def test_trusted_dirs_exist() -> None:
    assert (ROOT / "src" / "openverifiers" / "checker" / "check.py").exists()
    assert Path(ROOT / "scripts" / "tcb_size.py").exists()
