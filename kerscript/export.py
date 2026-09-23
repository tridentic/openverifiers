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

import re

import sympy as sp

from openverifiers.domains.physics_primitives import PRIMITIVES

from .units import token_of

ROOT = Path(__file__).resolve().parents[1]
OPK = ROOT / "opk"


def _type_name(token: str) -> str:
    return "t_" + re.sub(r"[^A-Za-z0-9]", "_", token)


def export_physics() -> str:
    lines = ["# KDScript-Domain — physics relations (exported from "
             "domains/physics_primitives.py; regenerate with "
             "`python -m kerscript.export`)", ""]
    lines.append("domain physics {")
    lines.append("")
    # unit reference table (built-in tokens, all used below)
    tokens = sorted({token_of(u)
                     for prim in PRIMITIVES.transformations.values()
                     for u in prim.rule["units"].values()})
    lines.append("    unit: " + ", ".join(tokens))
    lines.append("")
    # object model: nominal entity hierarchy (is-a, polymorphic roles)
    lines.append("    entity PointObject { }")
    lines.append("    entity ReferenceFrame { }")
    lines.append("")
    # quantity structs: one static type per unit dimension (frame/owner stay
    # hand-authored; exports are frame-free by declaration)
    for tok in tokens:
        lines.append(f"    type t_{_type_name(tok).replace('t_', '')} "
                     f"{{ value: quantity<{tok}> }}")
    lines.append("")
    for name, prim in sorted(PRIMITIVES.transformations.items()):
        rule = prim.rule
        inputs = ", ".join(
            f"{v}: t_{_type_name(token_of(rule['units'][v])).replace('t_', '')}"
            for v in rule["vars"])
        expr = sp.sstr(rule["expr"])
        doc = rule.get("doc", "")
        lines.append(f"    relation {name} {{")
        lines.append(f"        inputs: {{ {inputs} }}")
        lines.append(f"        equation: {expr} == 0")
        lines.append(f"        out: {rule['out']}")
        if doc:
            lines.append(f"        # {doc}")
        lines.append("    }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    OPK.mkdir(exist_ok=True)
    (OPK / "physics.opk").write_text(export_physics(), encoding="utf-8")
    print(f"wrote {OPK / 'physics.opk'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())