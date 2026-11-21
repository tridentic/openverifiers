"""Reductions on vs off: random small classes and theorems (condition A).

Each case is a random class over ``vertices: Set<Point>`` (3 or 4 points), with
0-2 ``exists v in cycles(vertices)`` invariants, a child class that repeats one
parent theorem word for word (so ``inherit`` is exercised), and 1-2 theorems in
``none`` or ``all ... ->`` form. Theorem conditions are drawn from the same atom
pool as the invariants, so the drop-implied, fix-order, translation and
invariant-free reductions all fire on some cases.

Every class check (consistency and each theorem) runs twice: reductions on
(``Settings()``) and off (``Settings(reductions=False, symmetry=False)``), each
with its own time limit. The claim tested: the two never reach different
definite verdicts. A side that times out (UNKNOWN) is counted, not failed.

    python -m openverifiers.bench.reductions --cases 100 --seed 0
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ..objects.engine import Settings
from ..runner import run_file

POINT = "type Point { x: Real, y: Real }\n"


def _atoms(n: int, rng: random.Random) -> list[str]:
    i, j, k = rng.sample(range(n), 3)
    c = rng.choice("xy")
    pool = [
        f"v[{i}].{c} = v[{j}].{c}",
        f"v[{i}].{c} != v[{j}].{c}",
        f"dist2(v[{i}], v[{j}]) = dist2(v[{j}], v[{k}])",
        f"dist2(v[{i}], v[{j}]) != dist2(v[{j}], v[{k}])",
        f"dist(v[{i}], v[{j}]) = dist(v[{j}], v[{k}]) > 0",
        f"angle(v[{i}], v[{j}], v[{k}]) = 90 deg",
        f"(v[{j}].x - v[{i}].x) * (v[{k}].y - v[{i}].y)"
        f" - (v[{k}].x - v[{i}].x) * (v[{j}].y - v[{i}].y) != 0",
    ]
    if n == 4:
        pool += [
            f"v[0].{c} + v[2].{c} = v[1].{c} + v[3].{c}",
            "dist2(v[0], v[2]) = dist2(v[1], v[3])",
            "dist(v[0], v[2]) != dist(v[1], v[3])",
            "(v[2].x - v[0].x) * (v[3].x - v[1].x) + (v[2].y - v[0].y) * (v[3].y - v[1].y) = 0",
        ]
    return pool


def _conds(n: int, rng: random.Random, k: int) -> list[str]:
    out: list[str] = []
    while len(out) < k:
        a = rng.choice(_atoms(n, rng))
        if a not in out:
            out.append(a)
    return out


def case(seed: int) -> str:
    """A random .ov source: a parent class, a child class, theorems on both."""
    rng = random.Random(seed)
    n = rng.choice([3, 4])
    invs = [_conds(n, rng, rng.randint(1, 2)) for _ in range(rng.randint(0, 2))]
    lines = [POINT, "fact type A {", "  property vertices: Set<Point>",
             f"  invariant size: count(vertices) = {n}"]
    for m, conds in enumerate(invs):
        lines.append(f"  invariant i{m}: exists v in cycles(vertices):")
        lines += [f"    {c}" for c in conds]
    theorems = []
    for m in range(rng.randint(1, 2)):
        conds = _conds(n, rng, rng.randint(1, 3))
        if invs and rng.random() < 0.5:         # reuse an invariant's conditions
            conds = list(dict.fromkeys([*rng.choice(invs), *conds]))
        if rng.random() < 0.5:
            body = [f"  theorem t{m}: none v in cycles(vertices):"] + [f"    {c}" for c in conds]
        else:
            *pre, post = conds if len(conds) > 1 else [*conds, conds[0]]
            neg = post.replace("!=", "=") if "!=" in post else post.replace(" = ", " != ", 1)
            pre = pre or ["v[0].x = v[0].x"]
            body = [f"  theorem t{m}: all v in cycles(vertices):"] + [f"    {c}" for c in pre]
            body.append(f"    -> {neg}")
        theorems.append(body)
        lines += body
    lines.append("}")
    extra = _conds(n, rng, 1)[0]
    lines += ["fact type B extends A {", "  invariant j: exists v in cycles(vertices):",
              f"    {extra}"]
    lines += theorems[0]
    lines.append("}")
    return "\n".join(lines) + "\n"


@dataclass
class Outcome:
    seed: int
    check: str
    on: str
    off: str
    on_trust: list[str]

    @property
    def conflict(self) -> bool:
        return "UNKNOWN" not in (self.on, self.off) and self.on != self.off


def run_case(seed: int, on_ms: int, off_ms: int, workdir: Path) -> list[Outcome] | str:
    src = case(seed)
    p = workdir / f"case{seed}.ov"
    p.write_text(src)
    try:
        on = run_file(p, files={str(p)}, settings=Settings(timeout_ms=on_ms)).classes
        off = run_file(p, files={str(p)}, settings=Settings(
            timeout_ms=off_ms, symmetry=False, reductions=False)).classes
    except Exception as e:                  # a generated case the language rejects
        return f"{type(e).__name__}: {e}".splitlines()[0]
    return [Outcome(seed, a.title, a.verdict, b.verdict, sorted(a.trust_base))
            for a, b in zip(on, off, strict=True)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openverifiers.bench.reductions")
    ap.add_argument("--cases", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--on-ms", type=int, default=5_000)
    ap.add_argument("--off-ms", type=int, default=20_000)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    rows: list[Outcome] = []
    rejected = 0
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        for s in range(a.seed, a.seed + a.cases):
            r = run_case(s, a.on_ms, a.off_ms, Path(d))
            if isinstance(r, str):
                rejected += 1
                print(f"seed {s}: rejected ({r})", file=sys.stderr)
                continue
            rows += r
    conflicts = [r for r in rows if r.conflict]
    unk = [r for r in rows if r.on != r.off and not r.conflict]
    used = sorted({t for r in rows for t in r.on_trust if t.startswith("red:")})
    summary = {
        "cases": a.cases, "rejected_cases": rejected, "checks": len(rows),
        "definite_both": sum("UNKNOWN" not in (r.on, r.off) for r in rows),
        "conflicts": len(conflicts),
        "unknown_only_disagreements": len(unk),
        "on_unknown_off_definite": sum(r.on == "UNKNOWN" for r in unk),
        "off_unknown_on_definite": sum(r.off == "UNKNOWN" for r in unk),
        "reductions_seen": used,
        "seconds": round(time.perf_counter() - start, 1),
    }
    print(json.dumps(summary, indent=2))
    for c in conflicts:
        print(f"CONFLICT seed {c.seed} {c.check}: on {c.on}, off {c.off}")
    if a.out:
        a.out.write_text("\n".join(json.dumps(o.__dict__) for o in rows) + "\n")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
