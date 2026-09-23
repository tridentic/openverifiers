"""v2 core — DSL, dispatch, scope discharge, whitelist, entrypoint."""

import pytest

from openverifiers import ActionFact, EnumValue, FactQuery
from openverifiers.domains import standard_grammars
from openverifiers.domains.math import make_number
from openverifiers.v2 import (Registry, parse_dsl, run_trace, submit,
                              extract_facts, Grammar)


@pytest.fixture(scope="module")
def reg():
    return Registry(standard_grammars())


class TestDSL:
    def test_step_and_kv(self):
        t = parse_dsl("s = kinematic.position(v0) with t=5, unit=\"m/s\"")
        assert t[0].transformation_name == "kinematic.position"
        assert t[0].params == {"t": 5, "unit": "m/s"}

    def test_dotted_names_and_comments(self):
        t = parse_dsl("# c\nx = math.add(a, b)")
        assert t[0].transformation_name == "math.add"

    def test_nested_scope_flattening(self):
        t = parse_dsl("""
        assume H: a is true
          a2 = math.add(x)
          assume J: deeper
            b2 = math.mul(y)
          end
        end
        """)
        ops = [(s.op, s.output_id, s.scope) for s in t]
        assert ("assume", "H", ()) in ops
        assert ("transform", "a2", ("H",)) in ops
        assert ("transform", "b2", ("H", "J")) in ops
        assert ("end", "J", ("H", "J")) in ops
        assert ("end", "H", ("H",)) in ops

    def test_unbalanced_end_rejected(self):
        with pytest.raises(ValueError, match="unbalanced"):
            parse_dsl("x = math.add(a)\nend")

    def test_unclosed_scope_rejected(self):
        with pytest.raises(ValueError, match="unclosed"):
            parse_dsl("assume H: p\n  y = math.mul(x)")

    def test_attempted_code_injection_is_unparsable(self):
        # the closed grammar simply has no token for this
        with pytest.raises(ValueError):
            parse_dsl("x = __import__(os).system(id)")


class TestDispatch:
    def test_arithmetic_trace(self, reg):
        r = run_trace(reg, reg.facts | {"a": make_number(3, "a"),
                                        "b": make_number(4, "b")},
                      parse_dsl("z = math.mul(a, b)"))
        assert r.verdict == "pass"
        assert r.env["z"].value == 12.0
        assert r.env["z"].derivation.input_fact_ids == ("a", "b")

    def test_unknown_transformation_rejected(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("z = bogus.transform(a)"))
        assert r.verdict == "invalid"
        assert "closed whitelist" in r.reason

    def test_dynamic_attribute_name_rejected(self, reg):
        # even a REGISTERED name cannot be reached through attribute chains;
        # anything outside the literal registry fails closed
        r = run_trace(reg, reg.facts, parse_dsl("z = math.getattr(a)"))
        assert r.verdict == "invalid"

    def test_unresolved_reference_fails(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("z = math.add(ghost)"))
        assert r.verdict != "pass"
        assert "unresolved" in (r.reason or "")

    def test_param_validation(self, reg):
        r = run_trace(reg, reg.facts,
                      parse_dsl("z = proof.base with n=0, nope=1"))
        assert r.verdict == "invalid"
        assert "unexpected param" in r.reason


class TestProof:
    def test_conditional_discharge(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("""
        assume H: n is even
          c = proof.base with n=1, expr="2"
        end
        """))
        assert r.verdict == "pass"
        imp = r.env["imp_H"]
        assert imp.premise == "n is even"
        assert imp.conclusion == "c"
        assert imp.dependencies == ()  # discharged = unconditional

    def test_conjunction_implication_for_mp(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("""
        assume A: P(0)
          c = proof.base with n=0, expr="1"
          step = proof.step(predecessor=c) with k=0, expr="1"
          b = logic.modus_ponens(implication=step, antecedent=c)
        end
        """))
        assert r.verdict == "pass"
        assert r.env["b"].value.value == "P(1)"

    def test_step_predecessor_must_match_k(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("""
        p5 = proof.base with n=5, expr="25"
        s = proof.step(predecessor=p5) with k=7, expr="x"
        """))
        assert r.verdict != "pass"
        assert "exact proposition it extends" in r.reason

    def test_induction_combine(self, reg):
        r = run_trace(reg, reg.facts, parse_dsl("""
        base = proof.base with n=0, expr="2n-1"
        step = proof.step(predecessor=base) with k=0, expr="2n-1"
        f = induction.combine(base=base, step=step) with variable=n, expr="2n-1"
        """))
        assert r.verdict == "pass"
        fa = r.env["f"]
        assert fa.quantifier == "forall"
        assert fa.variable == "n"
        assert fa.value.value == "forall n: P(n) = 2n-1"

    def test_forged_shape_only_step_rejected(self, reg):
        """P1 regression: an implication with the right SHAPE but no
        derivation chain must NOT close an induction."""
        from openverifiers import ActionFact, EnumValue
        forged = ActionFact(
            id="step", kind="implication", of="theorem", expr="2n-1",
            value=EnumValue(enum="math-implication",
                            value="P(0) -> P(1)"),
            source="forged")
        r = run_trace(reg, reg.facts | {"step": forged}, parse_dsl("""
        base = proof.base with n=0, expr="2n-1"
        f = induction.combine(base=base, step=step) with variable=n, expr="2n-1"
        """))
        assert r.verdict != "pass"
        assert "no derivation chain" in r.reason

    def test_expr_contradiction_rejected(self, reg):
        """P1 regression: forall closed form must equal the base's."""
        r = run_trace(reg, reg.facts, parse_dsl("""
        base = proof.base with n=0, expr="1"
        step = proof.step(predecessor=base) with k=0, expr="1"
        f = induction.combine(base=base, step=step) with variable=n, expr="2n-1"
        """))
        assert r.verdict != "pass"
        assert "contradicts base case" in r.reason

    def test_chain_must_reference_base_fact(self, reg):
        """P1 regression: step's derivation must name the SAME P(0) fact."""
        r = run_trace(reg, reg.facts, parse_dsl("""
        base = proof.base with n=0, expr="2n-1"
        alien = proof.base with n=0, expr="2n-1"
        step = proof.step(predecessor=alien) with k=0, expr="2n-1"
        f = induction.combine(base=base, step=step) with variable=n, expr="2n-1"
        """))
        assert r.verdict != "pass"
        assert "SAME P(0)" in r.reason

    def test_contradiction_discharge_negates_conflict(self):
        from openverifiers.v2 import ParamTransformation
        parity = Grammar(name="parity", transformations={
            "parity.declare": ParamTransformation(
                "parity.declare",
                apply=lambda inputs, params: ActionFact(
                    kind="parity", of=params.get("of", "n"),
                    value=EnumValue(enum="parity", value=params["value"]),
                    source=f"declare {params['value']}"),
                param_names=("of", "value"),
                doc="declare a parity attribute")},
            exclusive=(frozenset({"even", "odd"}),))
        reg2 = Registry([parity])
        bg = {"n_odd": ActionFact(
            kind="parity", of="n", value=EnumValue(enum="parity",
                                                   value="odd"))}
        r = run_trace(reg2, bg, parse_dsl("""
        assume H: n is even
          c = parity.declare with of=n, value="even"
        end contradiction
        """), exclusive=parity.exclusive)
        assert r.verdict == "pass"
        assert any(isinstance(f, ActionFact) and f.kind == "negation"
                   for f in r.env.values())


class TestEntrypoint:
    def test_submit_end_to_end(self):
        res = submit(FactQuery(make_number(12, "z"), 12),
                     traces="z = math.mul(a, b)",
                     background={"a": make_number(3, "a"),
                                 "b": make_number(4, "b")})
        assert res["verdict"] == "pass"
        assert res["reason"] == "z == 12 (canonical)"
        # 3 background + the math grammar's pi baseline fact (Grammar.facts)
        assert res["provenance_tiers"] == {"verified": 4}
        assert "math.mul" in res["render"]

    def test_extract_facts_stamps_tier(self):
        def adapter(_text):
            return [ActionFact(id="c0", kind="claim",
                               value=EnumValue(enum="relation",
                                               value="a is b"))]
        out = extract_facts(adapter, "a is b")
        assert out[0].provenance == "extracted"
        assert out[0].effective_provenance == "extracted"

    def test_duplicate_transformation_across_grammars_rejected(self):
        g2 = Grammar(name="g2", transformations={
            "math.add": __import__("openverifiers.model").Transformation(
                "math.add", apply=lambda inputs: make_number(0))})
        with pytest.raises(ValueError, match="duplicate"):
            Registry(list(standard_grammars()) + [g2])

    def test_submit_trace_failure_not_masked_by_mission(self):
        """P1 finding: a failed trace must dominate an otherwise-passing
        mission — gate can never be talked around via the target."""
        res = submit(FactQuery(make_number(12, "z"), 12),
                     traces="z = math.mul(a, ghost)",  # unresolved ref
                     background={"a": make_number(3, "a"),
                                 "b": make_number(4, "b"),
                                 "z": make_number(12, "z")})
        assert res["verdict"] != "pass"
        assert "unresolved" in res["reason"]