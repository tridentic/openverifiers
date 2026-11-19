#!/usr/bin/env python3
"""PART 5 — honest coverage report of the 200-problem syllabus dataset.

Checkable definition of "solvable today":
    every primitive in the problem's chain field is registered in the
    ALGEBRA + PHYSICS_PRIMITIVES grammars, AND the chain carries no
    OUT_OF_SCOPE marker.

Writes docs/coverage_report.md. Re-run after every grammar change.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from openverifiers.legacy.v2 import Registry                      # noqa: E402
from openverifiers.legacy.domains.algebra import ALGEBRA          # noqa: E402
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DS = REPO / "openverifiers" / "datasets" / "physics_syllabus_problems.csv"
OUT = REPO / "docs" / "coverage_report.md"


def main() -> int:
    implemented = set(Registry([ALGEBRA, PRIMITIVES]).transforms)
    rows = list(csv.DictReader(open(DS)))

    solvable, missing_deps, oos = [], [], []
    missing: Counter = Counter()
    for r in rows:
        chain = [c for c in r["chain"].split(";") if c]
        if not chain:
            continue
        if any(c.startswith("OUT_OF_SCOPE") for c in chain):
            oos.append(r)
            continue
        need = [c for c in chain if c not in implemented]
        if need:
            missing.update(need)
            missing_deps.append(r)
        else:
            solvable.append(r)

    total = len(rows)
    lines = [
        "# OpenVerifiers — honest syllabus coverage report",
        "",
        f"Dataset: **{total}** problems "
        f"(`datasets/physics_syllabus_problems.csv`, HSC 1st/2nd Paper + "
        f"JEE-A + BUET archetypes). Generated {None and '' or ''}— see "
        f"`datasets/generate_physics_dataset.py` for sourcing caveat.",
        "",
        f"- **Solvable today** (chain fully registered): "
        f"**{len(solvable)}** / {total} ({100 * len(solvable) / total:.0f}%)",
        f"- **Needs primitives not yet built**: **{len(missing_deps)}**",
        f"- **Structurally out of scope** (calculus/ODE or "
        f"non-algebraic): **{len(oos)}**",
        "",
        "## Needs primitives (ranked by how many problems block)",
        "",
        "| primitive | problems blocked |",
        "|---|---:|",
    ]
    for name, n in missing.most_common():
        lines.append(f"| `{name}` | {n} |")
    lines += [
        "",
        "## Structurally out of scope (flagged explicitly, not faked)",
        "",
        "| id | flag |",
        "|---|---:|",
    ]
    for r in sorted(oos, key=lambda r: r["id"]):
        flag = r["chain"].split(":")[-1]
        lines.append(f"| {r['id']} | `{flag}` |")
    lines += [
        "",
        "## Method",
        "",
        "Solvable means: every relation in the problem's solve chain is a "
        "registered primitive (one syllabus relation per transformation) and "
        "the required composition is expressible as trace steps (binding "
        "facts, leaving one variable free, closing with `algebra.equate`). "
        "It does **not** claim every parameterization of every archetype has "
        "been executed end-to-end — three representative archetypes are "
        "proven by example (`examples/chase_v2.py`, "
        "`examples/incline_energy.py`, `examples/heater_thermal.py`).",
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}  (solvable {len(solvable)}, needs {len(missing_deps)}, "
          f"OOS {len(oos)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())