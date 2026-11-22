"""Lemmas serve only their own package's proofs (CTO decision on MP-DOL deviation 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openverifiers.lang import OVError
from openverifiers.runner import run_file

BASE = """package lemmapkg
fact type Base {
  property a: Real
  property b: Real
  invariant shift: a = b + 1
  lemma gap: a - b = 1
}
fact type Inside extends Base {
  theorem gap_inside: a - b = 1
}
"""

CHILD = """import lemmapkg
fact type Outside extends Base {
  theorem gap_outside: a - b = 1
}
"""


def _theorems(tmp_path: Path, main: str) -> dict[str, list[str]]:
    (tmp_path / "lemmapkg.ov").write_text(BASE)
    f = tmp_path / "main.ov"
    f.write_text(main)
    res = run_file(f, files={str(f), str(tmp_path / "lemmapkg.ov")})
    out = {a.title: a.steps for a in res.classes if a.kind == "theorem"}
    assert all(a.verdict == "PROVEN" for a in res.classes if a.kind == "theorem")
    return out


def test_lemma_used_inside_its_package_only(tmp_path: Path) -> None:
    th = _theorems(tmp_path, CHILD)
    inside = " ".join(th["theorem Inside.gap_inside"])
    outside = " ".join(th["theorem Outside.gap_outside"])
    assert "Base.gap" in inside                  # same package: the lemma is reused
    assert "Base.gap" not in outside             # another package: proven on its own


def test_a_query_may_not_name_a_lemma(tmp_path: Path) -> None:
    main = "import lemmapkg\nscenario s uses lemmapkg {\n  query COUNTEREXAMPLE Base.gap\n}\n"
    with pytest.raises(OVError) as e:
        _theorems(tmp_path, main)
    assert "E407" in str(e.value)
