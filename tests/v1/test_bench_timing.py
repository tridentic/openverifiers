"""Wall-clock limits (change order v1.1 §2.3 and brief §10).

Marked ``bench``: the default run deselects them (pyproject ``addopts``), and
CI runs them in a separate job with no coverage instrumentation:
``pytest -m bench``. The limits are the targets; they are never relaxed to
make this job pass.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest

from openverifiers.engine import run
from openverifiers.raw import parse
from openverifiers.runner import run_file

from .programs import q11

pytestmark = pytest.mark.bench

ROOT = Path(__file__).resolve().parents[2]
# `ov check` on a single (rule) scenario. Object-layer files are reported in the
# bench summary, not held to this limit yet (see KNOWN_LIMITATIONS.md).
SINGLE_SCENARIO = ["examples/chem/q11.ov", "examples/physics/newton2.ov"]


def p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20, method="inclusive")[-1]


def test_ten_thousand_facts_under_5s() -> None:
    facts = "\n".join(f'fact e{i}: edge(n{i}, n{i + 1}) @"fact:t".' for i in range(10_000))
    p = parse(facts + """
        world red closed.
        rule r1: two(X, Z) :- edge(X, Y), edge(Y, Z).
        rule r2: red(X) :- edge(X, Y), Y = n5.
        rule r3: pair(X, Z) :- two(X, Z), not red(X).
    """)
    start = time.perf_counter()
    run(p)
    assert time.perf_counter() - start < 5.0


def test_q11_under_1s() -> None:
    start = time.perf_counter()
    run(q11())
    assert time.perf_counter() - start < 1.0


@pytest.mark.parametrize("path", SINGLE_SCENARIO)
def test_ov_check_p95_under_300ms(path: str) -> None:
    run_file(ROOT / path)                                  # warm imports and caches
    times = []
    for _ in range(20):
        start = time.perf_counter()
        run_file(ROOT / path)
        times.append(time.perf_counter() - start)
    assert p95(times) < 0.300, f"{path}: p95 {p95(times):.3f} s"
