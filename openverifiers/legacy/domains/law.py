"""Law domain slice (P5) — statute-element checklist rule.

Deliberately narrow: adjudication is contested fact-finding, so the grammar
marks every element assessment as unverified (provenance="extracted") unless
it is fed by a traced transformation. Judge-determined vs claimed stays
visible in render through the trust tiers.
"""

from __future__ import annotations

from ..facts import ActionFact, EnumValue
from ..model import Transformation, ParamTransformation, InputSpec
from ..v2 import Grammar

# One statute, two elements (illustrative slice).
STATUTE = {
    "negligence": (
        ("duty", "the defendant owed a duty of care"),
        ("breach", "the defendant breached that duty"),
    ),
}


def _element_met(inputs: dict, params: dict) -> ActionFact:
    statute = params.get("statute", "negligence")
    element = params.get("element")
    if statute not in STATUTE or element not in dict(STATUTE[statute]):
        raise ValueError(f"unknown element {element!r} of {statute!r}")
    claimed = inputs.get("allegation")
    met = bool(getattr(claimed, "value", False))
    return ActionFact(
        kind="element", of=statute,
        value=EnumValue(enum="element-verdict",
                        value="met" if met else "unmet"),
        source=f"{statute}:{element} checked against allegation "
               f"{claimed.id if claimed else '?'}",
        provenance="extracted")


def _all_elements(inputs: dict, params: dict) -> ActionFact:
    findings = [f for f in inputs.values()]
    met = all(isinstance(f.value, EnumValue) and f.value.value == "met"
              for f in findings)
    return ActionFact(
        kind="statute", of=params.get("statute", "negligence"),
        value=EnumValue(enum="statute-verdict",
                        value="satisfied" if met else "not-satisfied"),
        source="conjunction of element findings")


LAW = Grammar(
    name="law",
    doc="Statute-element checklist (contested facts stay on trust tier "
        "extracted).",
    transformations={
        "element_met": ParamTransformation(
            "law.element_met", apply=_element_met,
            param_names=("statute", "element"),
            precondition=lambda inputs: (
                None if inputs.get("allegation") is not None
                else "element assessment needs an allegation fact"),
            doc="mark one statute element met/unmet from an allegation",
            inputs=(InputSpec("allegation"),)),
        "all_elements": Transformation(
            "law.all_elements",
            apply=lambda inputs: _all_elements(inputs, {}),
            precondition=lambda inputs: (
                None if inputs else "law.all_elements needs element facts"),
            doc="conjunction of element findings"),
    },
)