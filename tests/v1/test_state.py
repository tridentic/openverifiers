"""OVState: export, hash, import (trusted loader), and refusals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openverifiers.lang import OVError
from openverifiers.raw.program import Atom
from openverifiers.raw.terms import Sym
from openverifiers.runner import run_file
from openverifiers.state.export import export, main
from openverifiers.state.hash import body, digest
from openverifiers.state.load import StateError, facts, load_atoms

FAM = """package fam
type Person
predicate parent(a: Person, b: Person) world closed
predicate ancestor(a: Person, b: Person) world closed
entity ann, bob, cy: Person
axiom base(a: Person, b: Person): parent(a, b) -> ancestor(a, b)
axiom step(a: Person, b: Person, c: Person): parent(a, b), ancestor(b, c) -> ancestor(a, c)
scenario family uses fam {
  fact parent(ann, bob)
  fact parent(bob, cy)
  assume maybe: parent(cy, ann)
}
"""
USE = """import fam
import state "fam.json" as kin
scenario later uses fam {
  query PROVE ancestor(ann, cy)
  query PROVE ancestor(cy, ann)
}
"""


def test_export_import_round_trip(tmp_path: Path) -> None:
    (tmp_path / "fam.ov").write_text(FAM)
    out = export(tmp_path / "fam.ov")
    assert len(out["body"]["atoms"]) == 5                 # type: ignore[index]  # no assumption
    (tmp_path / "fam.json").write_text(json.dumps(out))
    (tmp_path / "use.ov").write_text(USE)
    res = run_file(tmp_path / "use.ov", files={str(tmp_path / "use.ov")})
    assert [a.verdict for a in res.answers] == ["PROVEN", "REFUTED"]
    assert main([str(tmp_path / "fam.ov"), "--out", str(tmp_path / "x.json")]) == 0
    assert json.loads((tmp_path / "x.json").read_text())["sha256"] == out["sha256"]


def test_loader_refuses_tampering_and_non_canonical_files(tmp_path: Path) -> None:
    good = body([Atom("p", (Sym("a"),)), Atom("p", (Sym("b"),))])
    text = json.dumps({"sha256": digest(good), "body": good})
    assert len(facts("s", text)) == 2 and facts("s", text)[0].origin == "import:s"
    bad = json.loads(text)
    bad["body"]["atoms"][0]["args"] = [["sym", "z"]]
    for t in (json.dumps(bad), json.dumps({"body": good}),
              json.dumps({"sha256": "", "body": {"version": 2, "atoms": []}})):
        with pytest.raises((StateError, ValueError)):
            load_atoms(t)
    (tmp_path / "fam.ov").write_text(FAM)
    (tmp_path / "fam.json").write_text(json.dumps(bad))
    (tmp_path / "use.ov").write_text(USE)
    with pytest.raises(OVError) as e:
        run_file(tmp_path / "use.ov", files={str(tmp_path / "use.ov")})
    assert "E208" in str(e.value)
    (tmp_path / "use2.ov").write_text(USE.replace("fam.json", "missing.json"))
    with pytest.raises(OVError):
        run_file(tmp_path / "use2.ov", files={str(tmp_path / "use2.ov")})
