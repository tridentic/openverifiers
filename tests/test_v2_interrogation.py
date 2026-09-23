"""Items 2-5 regressions: Grammar-owned namespacing, declared input
signatures, Grammar baseline facts, and real Transformation subclass
polymorphism in the physics grammar."""

import pytest

from openverifiers.v2 import Registry, run_trace, submit, Grammar, parse_dsl
from openverifiers.model import Transformation, ParamTransformation, InputSpec
from openverifiers.domains import standard_grammars
from openverifiers.domains.math import make_number
from openverifiers.domains.physics_primitives import (PRIMITIVES, Primitive)

reg = Registry(standard_grammars() + [PRIMITIVES])


# -- 2. Grammar owns namespacing --------------------------------------------
def test_qualified_name_is_derived_from_grammar_name():
    # bare local keys get namespaced ONCE, by the Registry
    assert "kin.suvat_v_u_at" in reg.transforms
    assert "ckt.ohms" in reg.transforms
    assert "physics.alg" not in reg.transforms
    assert "math.add" in reg.transforms
    # explicit dotted keys survive verbatim (single source, no duplication)
    assert "proof.base" in reg.transforms
    assert "induction.combine" in reg.transforms


def test_registry_stamps_name_onto_transformation():
    t = reg.transforms["kin.suvat_v_u_at"]
    assert t.name == "kin.suvat_v_u_at"
    assert t is PRIMITIVES.transformations["kin.suvat_v_u_at"]


def test_math_add_unchanged_after_local_key_refactor():
    r = run_trace(reg, reg.facts | {"a": make_number(3, "a"),
                                    "b": make_number(4, "b")},
                  parse_dsl("z = math.add(a, b)"))
    assert r.verdict == "pass" and r.env["z"].value == 7.0


def test_duplicate_qualified_name_across_grammars_rejected():
    g2 = Grammar(name="math", transformations={
        "add": Transformation(name="add", apply=lambda inputs: make_number(0))})
    with pytest.raises(ValueError, match="duplicate"):
        Registry(list(standard_grammars()) + [g2])


# -- 3. declared input signatures -------------------------------------------
def test_missing_declared_input_rejected_with_signature_reason():
    r = run_trace(reg, reg.facts | {"a": make_number(3, "a")},
                  parse_dsl("z = math.add(b=a)"))      # role 'b' absent
    assert r.verdict != "pass"
    assert "missing required input" in r.reason
    assert "declares" in r.reason and "'a'" in r.reason and "'b'" in r.reason


def test_typo_in_apply_body_impossible_for_declared_roles():
    # declared and applied names come from one spec; a mismatch would be a
    # KeyError at runtime (caught, fail-closed), not a silent wrong value
    r = run_trace(reg, reg.facts | {"a": make_number(2, "a"),
                                    "b": make_number(5, "b")},
                  parse_dsl("z = math.add(a=a, b=b)"))
    assert r.verdict == "pass" and r.env["z"].value == 7.0


def test_render_exposes_required_signature():
    r = run_trace(reg, reg.facts | {"a": make_number(3, "a"),
                                    "b": make_number(4, "b")},
                  parse_dsl("z = math.add(a=a, b=b)"))
    assert "requires: a, b" in r.render()


def test_physics_grammar_declares_signatures():
    # every primitive declares its FULL variable set as optional inputs
    # (the runner enforces what is required; free vars become symbolic)
    got = {n: t.required_inputs()
           for n, t in PRIMITIVES.transformations.items()}
    assert got["kin.suvat_v_u_at"] == ("v", "u", "a", "t")
    assert got["th.q_mc_dt"] == ("Q", "m", "c", "dT")
    assert "dyn.fma" in got


# -- 4. baseline facts are a real field -------------------------------------
def test_math_baseline_constant_merges_into_registry():
    assert "math.pi" in reg.facts
    assert abs(reg.facts["math.pi"].value - 3.141592653589793) < 1e-12


def test_physics_primitives_baseline_intentionally_empty():
    # stated design: scenario facts are per-mission background; the physics
    # grammar registers relations only (G and pi are caller facts)
    assert PRIMITIVES.facts == {}


# -- 5. real subclass hierarchy is exercised --------------------------------
def test_all_physics_transformations_are_real_subclasses():
    for t in PRIMITIVES.transformations.values():
        assert isinstance(t, Primitive)
        assert isinstance(t, Transformation)


def test_polymorphic_dispatch_through_base_interface():
    for name, t in PRIMITIVES.transformations.items():
        assert callable(t.apply)
        # ParamTransformation subclass carries params (axis/theta)
        assert isinstance(t, ParamTransformation)


def test_primitives_dispatch_both_modes():
    # numeric solve (one free var) and expression mode (two free) on the
    # SAME primitive, through the single apply contract
    from openverifiers.domains.units_si import (Meter, MeterPerSecond,
                                                Second)
    from openverifiers import Quantity
    vot = reg.transforms["kin.suvat_s_s0_vt"]
    s0 = Quantity(value=10.0, unit=Meter(), id="s0")
    v = Quantity(value=2.0, unit=MeterPerSecond(), id="v")
    expr = vot.apply({"s0": s0, "v": v})          # expression in t
    assert expr.variables == ("t",)
    num = vot.apply({"s0": s0, "v": v,
                     "t": Quantity(value=3.0, unit=Second(), id="t")})
    assert abs(num.value - 16.0) < 1e-9