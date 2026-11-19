from __future__ import annotations

from openverifiers.m1.benchmarks.mutations import MUTATIONS, mutate
from openverifiers.m1.benchmarks.run import PERTURB, load_cases, render, run
from openverifiers.m1.domains import load


def test_every_mutation_kind_applies_to_some_math_case() -> None:
    pack = load("math")
    kinds = {m.kind for c in load_cases(["math"])["math"]
             for m in mutate(c, PERTURB["math"], pack)}
    assert kinds == set(MUTATIONS)


def test_mutants_differ_from_their_base() -> None:
    pack = load("math")
    for c in load_cases(["math"])["math"]:
        for m in mutate(c, PERTURB["math"], pack):
            assert (m.case.facts, m.case.requirements, m.case.proof) != (
                c.facts, c.requirements, c.proof), m.case.id


def test_math_benchmark_kernel_numbers() -> None:
    rep = run(["math"])
    assert rep.base["math"]["kernel"].rejected == 0  # no false rejections
    for (_, kind), t in rep.mutants.items():
        if kind != "misread_given":
            assert t["kernel"].rejected == t["kernel"].total, kind
    # the known, documented miss: speed after a drop does not depend on mass
    assert [m["mutant"] for m in rep.misses] == ["math_drop_speed~misread_given~0"]
    assert "| math | sign_error |" in render(rep)
