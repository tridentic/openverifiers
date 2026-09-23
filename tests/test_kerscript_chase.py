"""Chase round-trip proof — owner/frame survive KDScript compile end to end.

The regression this guards: a fact's semantic identity is "belongs to a
PointObject, measured in a ReferenceFrame" — never a variable name. The
chase grammar (opk/chase.opk) declares the structs, objects, typed
instances and a framed relation; these tests assert the compiled output
carries the object IDs through as REAL objects (identity, not strings).
"""
from pathlib import Path

import pytest

from openverifiers.v2 import Registry, parse_dsl, run_trace
from openverifiers.kerscript.compiler import entity_class, load_grammar
from openverifiers.kerscript.units import resolve_token

ROOT = Path(__file__).resolve().parents[1]
REG = Registry([load_grammar(ROOT / "opk/physics.opk"),
                load_grammar(ROOT / "opk/chase.opk")])

PointObject = entity_class("PointObject", "entity")
ReferenceFrame = entity_class("ReferenceFrame", "entity")


def _run(proof: str):
    return run_trace(REG, dict(REG.facts), parse_dsl(proof))


def test_owner_frame_round_trip():
    vt = REG.facts["v_tiger"]
    # semantic identity: this Velocity BELONGS TO the tiger object
    assert isinstance(vt.owner, PointObject), type(vt.owner)
    assert vt.owner.id == "tiger"
    # ... measured IN the ground frame
    assert isinstance(vt.frame, ReferenceFrame), type(vt.frame)
    assert vt.frame.id == "ground"
    # ... with the framed unit type (m/s), not a tag
    assert vt.unit.dimension == resolve_token("m/s").dimension


def test_deer_fact_bound_to_deer_only():
    vd = REG.facts["v_deer"]
    assert vd.owner.id == "deer" and vd.frame.id == "ground"
    assert vd.owner is not REG.facts["v_tiger"].owner


def test_polymorphic_owner_acceptance():
    # role typed PointObject accepts any PointObject subtype instance
    assert isinstance(REG.facts["v_tiger"].owner, PointObject)


def test_framed_relation_output_keeps_frame():
    r = _run("vrel = chase.v_rel(vt=v_tiger, vd=v_deer)")
    assert r.verdict == "pass", r.reason
    out = r.env["vrel"]
    assert abs(out.value - 5.0) <= 1e-6, out.value
    assert out.frame is not None and out.frame.id == "ground"
    # two distinct owners -> no common owner on the relative velocity
    assert out.owner is None


def test_relative_velocity_requires_distinct_owners():
    r = _run("vrel = chase.v_rel(vt=v_tiger, vd=v_tiger)")
    assert r.verdict != "pass"
    assert "different_owner" in r.reason


def test_relative_velocity_requires_same_frame():
    r = _run("vrel = chase.v_rel(vt=v_alt, vd=v_deer)")
    assert r.verdict != "pass"
    assert "frame_eq" in r.reason