"""Core logical primitives — cross-domain built-in transformations.

These are the reusable inference shapes KDScript-Domain documents reference
with `builtin(...)`. The rule: a builtin must be usable by at least two
domains' shapes, or it does not belong here — `relation`/`judge` cover the
rest.

v1 set (ported from the Python grammars, same semantics):

  * logic.modus_ponens       from A -> B and A derive B        (math/logic)
  * theorem_base             declare proposition P(n)          (math/logic)
  * theorem_step             P(k) -> P(k+1) on a predecessor   (math/logic)
  * induction_combine        base + chain step -> forall       (math/logic)
  * element_met              statute element vs allegation     (law)
  * all_elements             conjunction of element findings   (law)
"""
from __future__ import annotations

import re
from typing import Callable

from openverifiers.facts import (Fact, ActionFact, EnumValue, ForAllFact)
from openverifiers.model import Transformation, ParamTransformation, InputSpec

_PK = re.compile(r"^P\((\d+)\)")


# -- propositional / predicate inference -----------------------------------
def _mk_prop(label: str) -> EnumValue:
    return EnumValue(enum="math-proposition", value=label)


def make_modus_ponens() -> Transformation:
    def _mp(inputs: dict) -> Fact:
        impl: ActionFact = inputs["implication"]
        ante: ActionFact = inputs["antecedent"]
        assert isinstance(impl.value, EnumValue) and " -> " in impl.value.value
        lhs, _, rhs = impl.value.value.partition(" -> ")
        assert isinstance(ante.value, EnumValue) and ante.value.value == lhs, \
            f"antecedent {ante.value.value!r} does not fire implication " \
            f"{impl.value.value!r}"
        return ActionFact(kind="proposition", of="theorem",
                          value=EnumValue(enum="math-proposition", value=rhs),
                          source=f"modus ponens on {impl.id} with {ante.id}")
    return Transformation(
        "logic.modus_ponens", apply=_mp,
        precondition=lambda inputs: (
            None if isinstance(inputs.get("implication"), ActionFact)
            and isinstance(inputs.get("antecedent"), ActionFact)
            else "modus ponens needs an implication and an antecedent"),
        doc="from A -> B and A, derive B",
        inputs=(InputSpec("implication"), InputSpec("antecedent")))


def make_theorem_base() -> ParamTransformation:
    def _base(inputs: dict, params: dict) -> Fact:
        n = params.get("n", 0)
        expr = str(params.get("expr", ""))
        return ActionFact(kind="proposition", value=_mk_prop(f"P({n})"),
                          of="theorem", expr=expr,
                          source=f"base case n={n}, P({n}) = {expr}")
    return ParamTransformation(
        "proof.base", apply=_base, param_names=("n", "expr"),
        doc="declare a proposition P(n)")


def make_theorem_step() -> ParamTransformation:
    def _step(inputs: dict, params: dict) -> Fact:
        predecessor: ActionFact = inputs.get("predecessor")
        if not isinstance(predecessor, ActionFact) or \
                not isinstance(predecessor.value, EnumValue):
            raise ValueError("proof.step needs a proposition predecessor")
        k = params.get("k", 0)
        pv = predecessor.value.value
        if pv != f"P({int(k)})":
            raise ValueError(
                f"predecessor is {pv!r}, step declares P({int(k)}) — step "
                f"must consume the exact proposition it extends")
        return ActionFact(
            kind="implication", of="theorem",
            value=EnumValue(enum="math-implication",
                            value=f"P({int(k)}) -> P({int(k) + 1})"),
            expr=str(params.get("expr", "")),
            source=f"P({int(k)}) => P({int(k) + 1}) declared on "
                   f"{predecessor.id}")
    return ParamTransformation(
        "proof.step", apply=_step, param_names=("k", "expr"),
        precondition=lambda inputs: (
            None if inputs.get("predecessor") is not None
            else "proof.step needs a predecessor proposition it extends"),
        doc="P(k) -> P(k+1) declared on its predecessor (chain-recorded)",
        inputs=(InputSpec("predecessor"),))


def make_induction_combine() -> ParamTransformation:
    def _combine(inputs: dict, params: dict) -> Fact:
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
            f"forall closed form {expr!r} contradicts step's declared " \
            f"extension {getattr(step, 'expr', '?')!r}"
        der = step.derivation
        assert der is not None and der.input_fact_ids, \
            "step carries no derivation chain — shape-only implication " \
            "cannot close an induction"
        assert base.id in der.input_fact_ids, \
            f"step's derivation chain references {der.input_fact_ids}, not " \
            f"the base fact {base.id!r} — induction must close over the " \
            f"SAME P(0)"
        return ForAllFact(
            quantifier="forall", variable=var,
            value=EnumValue(enum="math-proposition",
                            value=f"forall {var}: P({var}) = {expr}"),
            source=f"induction over chain {base.id} <- {step.id}: "
                   f"forall {var}: P({var}) = {expr}")
    return ParamTransformation(
        "induction.combine", apply=_combine, param_names=("variable", "expr"),
        doc="base + step => forall n: P(n)",
        inputs=(InputSpec("base"), InputSpec("step")))


# -- law: statute-element checklist ----------------------------------------
def make_element_met(statute: dict | None = None) -> ParamTransformation:
    statute = statute or {"negligence": (
        ("duty", "the defendant owed a duty of care"),
        ("breach", "the defendant breached that duty"),
    )}

    def _element(inputs: dict, params: dict) -> ActionFact:
        s = params.get("statute", "negligence")
        element = params.get("element")
        if s not in statute or element not in dict(statute[s]):
            raise ValueError(f"unknown element {element!r} of {s!r}")
        claimed = inputs.get("allegation")
        met = bool(getattr(claimed, "value", False))
        return ActionFact(
            kind="element", of=s,
            value=EnumValue(enum="element-verdict",
                            value="met" if met else "unmet"),
            source=f"{s}:{element} checked against allegation "
                   f"{claimed.id if claimed else '?'}",
            provenance="extracted")
    return ParamTransformation(
        "law.element_met", apply=_element, param_names=("statute", "element"),
        precondition=lambda inputs: (
            None if inputs.get("allegation") is not None
            else "element assessment needs an allegation fact"),
        doc="mark one statute element met/unmet from an allegation",
        inputs=(InputSpec("allegation"),))


def make_all_elements(statute: dict | None = None) -> ParamTransformation:
    statute = statute or {"negligence": (
        ("duty", "the defendant owed a duty of care"),
        ("breach", "the defendant breached that duty"),
    )}

    def _conj(inputs: dict, params: dict) -> ActionFact:
        s = params.get("statute", "negligence")
        declared = dict(statute.get(s, ()))
        findings = {f.id: f for f in inputs.values()}
        missing = [e for e in declared if e not in findings]
        if missing:
            return ActionFact(
                kind="statute", of=s,
                value=EnumValue(enum="statute-verdict",
                                value="not-satisfied"),
                source=f"conjunction of element findings — declared elements "
                       f"unchecked: {missing}")
        met = all(isinstance(f.value, EnumValue) and f.value.value == "met"
                  for f in findings.values())
        return ActionFact(
            kind="statute", of=s,
            value=EnumValue(enum="statute-verdict",
                            value="satisfied" if met else "not-satisfied"),
            source="conjunction of element findings")
    return ParamTransformation(
        "law.all_elements", apply=_conj, param_names=("statute",),
        precondition=lambda inputs: (
            None if inputs else "law.all_elements needs element facts"),
        doc="conjunction of element findings (all declared elements must be "
            "checked and met)")


_BUILTINS: dict[str, Callable[[], Transformation]] = {
    "logic.modus_ponens": make_modus_ponens,
    "theorem_base": make_theorem_base,
    "theorem_step": make_theorem_step,
    "induction_combine": make_induction_combine,
    "element_met": make_element_met,
    "all_elements": make_all_elements,
}


def make_builtin(name: str) -> Transformation:
    if name not in _BUILTINS:
        raise ValueError(
            f"unknown builtin {name!r}; available: {sorted(_BUILTINS)}")
    return _BUILTINS[name]()