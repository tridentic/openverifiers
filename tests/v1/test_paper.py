"""OV-Paper hooks: the SUVAT blueprint and statement closure, dumped as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from openverifiers.paper import blueprints
from openverifiers.runner import run_file

ROOT = Path(__file__).resolve().parents[2]
MECH = ROOT / "src" / "openverifiers" / "packages" / "physics" / "mechanics.ov"


def test_suvat_blueprint_and_closure(tmp_path: Path) -> None:
    res = run_file(MECH, files={str(MECH)})
    bps = {b["theorem"]: b for b in blueprints(res)}
    out = tmp_path / "suvat_blueprint.json"
    out.write_text(json.dumps({k: v for k, v in bps.items() if "suvat" in k}, indent=1))
    suvat = bps["ConstantAcceleration.suvat_s"]
    assert suvat["statement"]["text"].startswith("theorem suvat_s:")
    assert suvat["statement"]["proposed_by"] == "founder-approved"
    assert suvat["verdict"] == "PROVEN" and suvat["trust"] == ["kernel"]
    closure = suvat["closure"]
    assert closure["exact"] is True
    assert "ConstantAcceleration.displacement" in closure["definition"]
    assert "ConstantAcceleration.velocity" not in closure["definition"]   # not needed for s
    roles = {s["role"] for s in suvat["steps"]}
    assert {"definition", "key"} <= roles
    key = next(s for s in suvat["steps"] if s["role"] == "key")
    assert key["proposed_by"] == "sympy finder, checked by the kernel"
    work = bps["ConstantForce.work_energy"]
    assert "ConstantForce.newton2" in work["closure"]["law"]               # a law, by role
    loaded = json.loads(out.read_text())
    assert set(loaded) >= {"ConstantAcceleration.suvat_v", "ConstantAcceleration.suvat_s"}
