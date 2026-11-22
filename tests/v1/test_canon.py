"""W2.5: canonical JSON is the only way programs and traces enter trusted code."""

from __future__ import annotations

import ast
import json
from fractions import Fraction
from pathlib import Path

import pytest

from openverifiers.checker import TraceRejected, check_json
from openverifiers.kernel import evaluate
from openverifiers.raw import Program, canon
from openverifiers.raw.terms import Compound, Num, Str, Sym, Var
from openverifiers.raw.trace import dumps, loads

from .programs import PENGUIN, REACH, q11

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "openverifiers"


@pytest.mark.parametrize("prog", [PENGUIN, REACH, q11()], ids=["penguin", "reach", "q11"])
def test_program_and_trace_round_trip(prog: Program) -> None:
    text = json.dumps(canon.program_to_json(prog), sort_keys=True)
    assert canon.program_from_json(json.loads(text)) == prog
    tr = evaluate(prog)
    assert loads(dumps(tr)) == tr
    model = check_json(text, dumps(tr))
    assert model.program == prog


def test_terms_have_one_encoding() -> None:
    t = Compound("f", (Sym("a"), Str("s"), Var("X"),
                       Num(Fraction(-3, 2), (("L", Fraction(1)), ("T", Fraction(-2))))))
    assert canon.term_from_json(canon.term_to_json(t)) == t
    for bad in (["num", "1.5", []], ["num", "6/4", []], ["num", " 1", []],
                ["num", "1", [["T", "1"], ["L", "1"]]],          # dims out of order
                ["num", "1", [["L", "0"]]],                      # zero exponent
                ["sym", 3], ["app", "f", "x"], ["frob", "x"], [], "a",
                ["num", "1", [["L"]]]):
        with pytest.raises(ValueError):
            canon.term_from_json(bad)
    for bad_atom in ({"pred": "p", "args": []}, {"pred": "p", "args": [], "neg": 0},
                     {"pred": "p", "args": [], "neg": False, "x": 1}):
        with pytest.raises(ValueError):
            canon.atom_from_json(bad_atom)
    for bad_span in ([1, 2], ["f", 1, 2, 3, True], ["f", 1, 2, 3, "4"]):
        with pytest.raises(ValueError):
            canon.span_from_json(bad_span)


def test_program_json_rejections() -> None:
    good = canon.program_to_json(PENGUIN)
    with pytest.raises(ValueError):
        canon.program_from_json({**good, "extra": []})
    for key, bad in (("worlds", [["p", "yes"]]), ("worlds", [["p"]]),
                     ("domains", [["d", "p", [], [], 1, None]]),
                     ("rules", [["r", {"pred": "p", "args": [], "neg": False}, [["frob"]], None]])):
        with pytest.raises(ValueError):
            canon.program_from_json({**good, key: bad})


def test_tampered_json_trace_is_rejected() -> None:
    text = json.dumps(canon.program_to_json(PENGUIN))
    rows = dumps(evaluate(PENGUIN)).splitlines()
    step = json.loads(rows[-1])
    step["conclusion"]["args"] = [["sym", "nobody"]]
    rows[-1] = json.dumps(step)
    with pytest.raises(TraceRejected):
        check_json(text, "\n".join(rows))


def test_trusted_code_has_no_text_grammar() -> None:
    """No trusted module imports the RawOV text parser or a regex engine."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("tcb", ROOT / "scripts" / "tcb_size.py")
    assert spec and spec.loader
    tcb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tcb)
    files = [*tcb.trusted_files(), *(SRC / u for u in tcb.UNITS), *(SRC / u for u in tcb.EXACT)]
    assert len(files) >= 12
    for f in files:
        tree = ast.parse(f.read_text())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m and ("rawtext" in m or m in ("re", "lark")) for m in mods), f
