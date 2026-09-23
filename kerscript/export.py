"""Regenerate opk/ grammar documents from the Python grammars.

Honest parity tool: every exported relation is read back from the SAME rule
table the Python grammar uses (PRIMITIVES), so a compiled opk grammar and the
Python grammar agree relation-for-relation. The opk file is the portable
artifact; this script is the one-time bridge, kept to prove parity on
regenerate.
"""
from __future__ import annotations

import sys
from pathlib import Path

import sympy as sp

from openverifiers.domains.physics_primitives import PRIMITIVES

from .units import token_of

ROOT = Path(__file__).resolve().parents[1]
OPK = ROOT / "opk"


def export_physics() -> str:
    lines = ["# KDScript-Domain — physics relations (exported from "
             "domains/physics_primitives.py; regenerate with "
             "`python -m kerscript.export`)", ""]
    title = getattr(PRIMITIVES, "doc", "") or "physics"
    lines.append(f"domain physics   # {title}")
    lines.append("")
    for name, prim in sorted(PRIMITIVES.transformations.items()):
        rule = prim.rule
        tokens = {v: token_of(u) for v, u in rule["units"].items()}
        unit_args = ", ".join(f"{v}={tokens[v]}" for v in rule["vars"])
        expr = sp.sstr(rule["expr"]).replace("**", "**")
        doc = rule.get("doc", "")
        lines.append(f"relation {name}: {expr}  "
                     f"unit({unit_args})  out({rule['out']})")
        if doc:
            lines.append(f"    # {doc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    OPK.mkdir(exist_ok=True)
    (OPK / "physics.opk").write_text(export_physics(), encoding="utf-8")
    print(f"wrote {OPK / 'physics.opk'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())