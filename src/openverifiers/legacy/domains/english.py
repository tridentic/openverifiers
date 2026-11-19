"""English-language domain slice (P5) — extraction-mediated claims.

The point of this slice is the trust boundary, not NLP: extraction adapters
(rule-based here; an LLM adapter is pluggable) produce facts stamped
provenance="extracted". A traced transformation may then reason over them,
and render keeps the tier visible.
"""

from __future__ import annotations

import re

from ..facts import ActionFact, EnumValue
from ..model import Transformation, InputSpec
from ..v2 import Grammar

_SENTENCE = re.compile(r"([A-Za-z]+)\s+(is|are|was|were|has|have)\s+"
                       r"([A-Za-z]+)")


def rule_adapter(text: str):
    """Demo adapter: np is/are/was/were/has/have np -> subject(link)object."""
    out = []
    for i, m in enumerate(_SENTENCE.finditer(text)):
        subj, link, obj = m.groups()
        out.append(ActionFact(
            id=f"claim{i}", kind="claim",
            value=EnumValue(enum="relation",
                            value=f"{subj} {link} {obj}"),
            of=subj, source="english-extraction-rule"))
    return out


def _agreement(inputs: dict) -> ActionFact:
    subj: ActionFact = inputs["subject"]
    obj: ActionFact = inputs["object"]
    s_ok = getattr(subj.value, "value", subj.value).split()[0].isalpha()
    return ActionFact(
        kind="agreement", of=f"{subj.id}~{obj.id}",
        value=EnumValue(enum="agreement-verdict",
                        value="consistent" if s_ok else "inconsistent"),
        source=f"subject-verb agreement check ({subj.id}, {obj.id})")


ENGLISH = Grammar(
    name="english",
    doc="Extraction-mediated natural-language claims.",
    transformations={
        "agreement": Transformation(
            "english.agreement",
            apply=_agreement,
            precondition=lambda inputs: (
                None if inputs.get("subject") and inputs.get("object")
                else "agreement needs subject and object claims"),
            doc="subject-verb agreement verdict between two claims",
            inputs=(InputSpec("subject"), InputSpec("object")),),
    },
)