"""A tiny domain pack used only to exercise kernel rules."""

from __future__ import annotations

import math
from collections.abc import Mapping

from openverifiers.m1.kernel import DomainPack, Fact, FactType, Precondition, Transformation
from openverifiers.m1.kernel.model import Inputs, Params


def num(fid: str, value: object = None, **kw: object) -> Fact:
    return Fact(id=fid, type="num", value=value, **kw)  # type: ignore[arg-type]


def _is_num(f: Fact) -> str | None:
    ok = isinstance(f.value, int | float) and not isinstance(f.value, bool)
    return None if ok else f"value {f.value!r} is not a number"


def _finite(inputs: Inputs, params: Params) -> str | None:
    bad = [f.id for f in inputs.values() if not math.isfinite(f.value)]
    return f"non-finite inputs {bad}" if bad else None


def _nonneg(inputs: Inputs, params: Params) -> str | None:
    return None if inputs["x"].value >= 0 else f"x = {inputs['x'].value} < 0"


def _raises(inputs: Inputs, params: Params) -> str | None:
    raise RuntimeError("boom")


def _lookup_checker(inputs: Inputs, params: Params, out: Mapping[str, Fact]) -> str | None:
    v = out["value"]
    cite = v.provenance.citation if v.provenance else None
    text = SOURCES.get(cite or "", "")
    return None if f"= {v.value}" in text else f"source {cite!r} does not state {v.value}"


SOURCES = {"table": "c = 3"}

PACK = DomainPack(
    name="toy",
    fact_types={"num": FactType("num", validate=_is_num), "note": FactType("note")},
    transformations={t.id: t for t in [
        Transformation("add", "hard", {"a": "num", "b": "num"}, {"sum": "num"},
                       preconditions=(Precondition("finite", _finite),),
                       effect=lambda i, p: {"sum": num("_", i["a"].value + i["b"].value)}),
        Transformation("sqrt", "hard", {"x": "num"}, {"y": "num"},
                       preconditions=(Precondition("nonnegative", _nonneg),),
                       effect=lambda i, p: {"y": num("_", math.sqrt(i["x"].value))}),
        Transformation("explode", "hard", {"x": "num"}, {"y": "num"},
                       preconditions=(Precondition("raises", _raises),),
                       effect=lambda i, p: {"y": i["x"]}),
        Transformation("broken", "hard", {"x": "num"}, {"y": "num"},
                       effect=lambda i, p: {"y": num("_", 1 / 0)}),
        Transformation("succ", "hard", {"x": "num"}, {"y": "num"},
                       checker=lambda i, p, o: None if o["y"].value == i["x"].value + 1
                       else f"{o['y'].value} != {i['x'].value} + 1"),
        Transformation("crashy_check", "hard", {"x": "num"}, {"y": "num"},
                       checker=lambda i, p, o: str(1 / 0)),
        Transformation("lookup", "grounded", {}, {"value": "num"}, checker=_lookup_checker),
        Transformation("guess", "soft", {"x": "num"}, {"y": "num"},
                       checker=lambda i, p, o: None),
        Transformation("annotate", "hard", {"x": "*"}, {"n": "note"},
                       effect=lambda i, p: {"n": Fact("_", "note", value=f"saw {i['x'].id}")}),
    ]},
    predicates={
        "positive": lambda f, a: None if f.value > 0 else f"{f.value} <= 0",
        "crashes": lambda f, a: str(1 / 0),
    },
    sources=SOURCES,
)
