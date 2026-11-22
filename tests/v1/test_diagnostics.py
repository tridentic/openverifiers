"""C2 diagnostics: unit/property clashes (E304) and division by a non-constant."""

from __future__ import annotations

from pathlib import Path

import pytest

from openverifiers.lang import OVError
from openverifiers.runner import run_file


def _run(tmp_path: Path, body: str, scenario: str = "") -> object:
    f = tmp_path / "d.ov"
    f.write_text(f"package probe.d\nfact type G {{\n{body}\n}}\n{scenario}")
    return run_file(f, files={str(f)})


def test_unit_property_clash_is_an_error_with_a_fix(tmp_path: Path) -> None:
    body = "  property p: Pressure\n  property t: Temperature\n  invariant pos: p > 0 t > 0"
    with pytest.raises(OVError) as e:
        _run(tmp_path, body)
    assert "E304" in str(e.value) and "(0) t" in str(e.value)
    res = _run(tmp_path, body.replace("p > 0 t > 0", "p > (0) t > 0"))
    assert res.classes[0].verdict == "PROVEN"                          # type: ignore[attr-defined]
    # A real unit after a number is still a quantity when no property shares its name.
    _run(tmp_path, "  property m: Mass\n  invariant pos: m > 0 kg")


def test_division_by_a_non_constant_is_multiplied_through(tmp_path: Path) -> None:
    body = ("  property x: Real\n  property y: Real\n  property q: Real\n"
            "  invariant pos: y > 0\n  invariant ratio: q = x / y\n"
            "  theorem back: q * y = x")
    res = _run(tmp_path, body, "scenario s uses probe.d {\n"
                               "  query FIND ?q WHERE G{ x = 6, y = 4, q = ?q }\n}\n")
    find = res.objects[0]                                              # type: ignore[attr-defined]
    assert find.verdict == "PROVEN" and str(find.bindings[0]["q"].value) == "3/2"
    th = next(a for a in res.classes if a.kind == "theorem")           # type: ignore[attr-defined]
    assert th.verdict == "PROVEN"
    assert any("side condition" in s and "!= 0" in s for s in th.steps)   # recorded
