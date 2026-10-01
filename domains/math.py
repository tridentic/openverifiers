"""Math domain v2 grammars — arithmetic facts and proof machinery (P5 slice).

Trust discipline: numeric transformations act on dimensionless Quantity facts
(unit=DIMENSIONLESS is the codebase's dimensionless convention) and produce
Quantities only. Proof transformations manipulate EnumValue-proposition facts
and the Implication/Fact types the trace runner itself produces — the pattern
gates (P(k) -> P(k+1)) are the pragmatic line between honest structure and
pretending to a general theorem prover.
"""

from __future__ import annotations

import re

from ..facts import (Fact, Quantity, ActionFact, EnumValue,
                     ForAllFact, DerivationRecord, DIMENSIONLESS)
from ..model import Transformation, ParamTransformation, InputSpec
from ..v2 import Grammar


def _leq_num(a: Fact, b: Fact) -> bool:
    """|a - b| <= 1e-6 when both are numbers (math.eq semantics)."""
    na, nb = _num(a), _num(b)
    return na is not None and nb is not None and abs(na - nb) <= 1e-6


def _num(f: Fact) -> float | None:
    if isinstance(f, Quantity) and f.value is not None:
        return float(f.value)
    return None


def _dimless(f: Fact) -> Quantity:
    if not isinstance(f, Quantity) or f.value is None:
        raise ValueError("math transformations need numeric facts")
    return Quantity(value=float(f.value), unit=DIMENSIONLESS)


def _mk(name: str, apply, **kw):
    return Transformation(name, apply=apply, **kw)


def _arith(fn, name, doc, *, inputs=()):
    def apply(inputs: dict) -> Fact:
        a, b = _num(inputs["a"]), _num(inputs["b"])
        assert a is not None and b is not None
        return Quantity(value=fn(a, b), unit=DIMENSIONLESS,
                        derivation=DerivationRecord(
                            controller_name="math", rule_name=name,
                            input_fact_ids=(inputs["a"].id, inputs["b"].id)))
    return Transformation(name, apply=apply, doc=doc, inputs=inputs)


# -- proof machinery -------------------------------------------------------

_PK = re.compile(r"^P\((\d+)\)")


def _mk_prop(label: str) -> EnumValue:
    return EnumValue(enum="math-proposition", value=label)


def _theorem_base(inputs: dict, params: dict) -> Fact:
    n = params.get("n", 0)
    expr = str(params.get("expr", ""))
    return ActionFact(kind="proposition", value=_mk_prop(f"P({n})"),
                      of="theorem", expr=expr,
                      source=f"base case n={n}, P({n}) = {expr}")


def _theorem_step(inputs: dict, params: dict) -> Fact:
    """Declare the induction step. NOT an algebra engine: it asserts
    P(k) => P(k+1) for a CREATED closed form — but the assertion must name its
    predecessor fact, so the produced implication carries a real derivation
    chain (runner stamps derivation.input_fact_ids with the predecessor's id).
    """
    predecessor = inputs.get("predecessor")
    if not isinstance(predecessor, ActionFact) or \
            not isinstance(predecessor.value, EnumValue):
        raise ValueError("proof.step needs a proposition predecessor")
    k = params.get("k", 0)
    pv = predecessor.value.value
    if pv != f"P({int(k)})":
        raise ValueError(f"predecessor is {pv!r}, step declares P({int(k)}) — "
                         f"step must consume the exact proposition it extends")
    return ActionFact(
        kind="implication", of="theorem",
        value=EnumValue(enum="math-implication",
                        value=f"P({int(k)}) -> P({int(k) + 1})"),
        expr=str(params.get("expr", "")),
        source=f"P({int(k)}) => P({int(k) + 1}) declared on "
               f"{predecessor.id}")


def _modus_ponens(inputs: dict) -> Fact:
    impl: ActionFact = inputs["implication"]
    ante: ActionFact = inputs["antecedent"]
    assert isinstance(impl.value, EnumValue) and " -> " in impl.value.value
    lhs, _ = impl.value.value.split(" -> ", 1)
    assert isinstance(ante.value, EnumValue) and ante.value.value == lhs, \
        f"antecedent {ante.value.value!r} does not fire implication " \
        f"{impl.value.value!r}"
    return ActionFact(kind="proposition", of="theorem",
                      value=EnumValue(enum="math-proposition",
                                      value=impl.value.value.split(" -> ", 1)[1]),
                      source=f"modus ponens on {impl.id} with {ante.id}")


def _induction_combine(inputs: dict, params: dict) -> Fact:
    """Close induction ONLY over a chain-valid step.

    Checks, in order:
      1. shape  — base is a P(0) proposition, step is a P(0) -> P(1)
         implication (matches tags AND values);
      2. content — the forall's closed form is the SAME expression the base
         was declared with and the step was declared to extend
         (base.expr == step.expr == params.expr);
      3. chain — the step carries a DerivationRecord whose input_fact_ids
         contain the base fact itself: the implication is a registered-
         transformation product of this trace, not an orphan tag.

    Checks 2 and 3 are what separate "right shape" from "derived here".
    """
    base: ActionFact = inputs["base"]
    step: ActionFact = inputs["step"]
    var = params.get("variable", "n")
    expr = str(params.get("expr", ""))
    assert isinstance(base.value, EnumValue) and \
        base.value.value == "P(0)", \
        "induction requires a base case proven AT P(0)"
    assert isinstance(step.value, EnumValue) and \
        step.value.value == "P(0) -> P(1)", \
        "induction requires a P(0) -> P(1) step"
    assert getattr(base, "expr", "") and getattr(base, "expr", "") == expr, \
        f"forall closed form {expr!r} contradicts base case " \
        f"P(0) = {getattr(base, 'expr', '?')!r}"
    assert getattr(step, "expr", "") == expr, \
        f"forall closed form {expr!r} contradicts step's declared extension " \
        f"{getattr(step, 'expr', '?')!r}"
    der = step.derivation
    assert der is not None and der.input_fact_ids, \
        "step carries no derivation chain — shape-only implication cannot " \
        "close an induction"
    assert base.id in der.input_fact_ids, \
        f"step's derivation chain references {der.input_fact_ids}, not the " \
        f"base fact {base.id!r} — induction must close over the SAME P(0)"
    return ForAllFact(quantifier="forall", variable=var,
                      value=EnumValue(enum="math-proposition",
                                      value=f"forall {var}: P({var}) = {expr}"),
                      source=f"induction over chain {base.id} <- "
                             f"{step.id}: forall {var}: P({var}) = {expr}")


MATH = Grammar(
    name="math",
    doc="Arithmetic + deductive proof patterns (modus ponens, induction).",
    transformations={
        "add": _arith(lambda a, b: a + b, "add",
                           "a + b (dimensionless quantities)",
                           inputs=(InputSpec("a"), InputSpec("b"))),
        "mul": _arith(lambda a, b: a * b, "mul",
                      "a * b (dimensionless quantities)",
                      inputs=(InputSpec("a"), InputSpec("b"))),
        "eq": Transformation(
            "eq",
            apply=lambda inputs: ActionFact(
                kind="equality", of=f"{inputs['a'].id}_{inputs['b'].id}",
                value=EnumValue(enum="truth", value="equal")
                if _leq_num(inputs["a"], inputs["b"])
                else _mk_prop("mismatch")),
            doc="compare two dimensionless quantities",
            inputs=(InputSpec("a"), InputSpec("b")),),
        "proof.base": ParamTransformation(
            "proof.base", apply=_theorem_base,
            param_names=("n", "expr"), doc="declare a proposition P(n)"),
        "proof.step": ParamTransformation(
            "proof.step", apply=_theorem_step,
            param_names=("k", "expr"),
            precondition=lambda inputs: (
                None if inputs.get("predecessor") is not None
                else "proof.step needs a predecessor proposition it extends"),
            doc="P(k) -> P(k+1) declared on its predecessor (chain-recorded)"),
        "logic.modus_ponens": Transformation(
            "logic.modus_ponens", apply=_modus_ponens,
            precondition=lambda inputs: (
                None if isinstance(inputs.get("implication"), ActionFact)
                and isinstance(inputs.get("antecedent"), ActionFact)
                else "modus ponens needs an implication and an antecedent"),
            doc="from A->B and A, derive B",
            inputs=(InputSpec("implication"), InputSpec("antecedent")),),
        "induction.combine": ParamTransformation(
            "induction.combine", apply=_induction_combine,
            param_names=("variable", "expr"),
            doc="base + step => forall n: P(n)",
            inputs=(InputSpec("base"), InputSpec("step")),),
    },
    facts={
        "math.pi": Quantity(value=3.141592653589793, unit=DIMENSIONLESS,
                            id="math.pi", source="mathematical constant"),
    },
    exclusive=(frozenset({"even", "odd"}),),
)


def make_number(value: float, id: str = "?") -> Quantity:
    """Public builder for dimensionless numeric facts in math traces."""
    return Quantity(value=value, unit=DIMENSIONLESS, id=id)