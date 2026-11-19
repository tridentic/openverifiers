"""Business domain slice (P5) — compound-interest scenario arithmetic.

One transformation, honestly dimensioned: money is a Quantity in dollars.
Trace steps, not ad-hoc code, drive each scenario; provenance stays visible.
"""

from __future__ import annotations

from ..facts import Quantity, DerivationRecord
from ..model import ParamTransformation, InputSpec
from ..v2 import Grammar
from .units_si import Dollar


def _compound(inputs: dict, params: dict) -> Quantity:
    p: Quantity = inputs["principal"]
    r_pct = float(params.get("rate_pct", 0.0))
    years = float(params.get("years", 1))
    pv = p.value if p.value is not None else 0.0
    fv = pv * (1 + r_pct / 100.0) ** years
    return Quantity(value=round(fv, 2), unit=Dollar(),
                    derivation=DerivationRecord(
                        controller_name="business",
                        rule_name="business.compound",
                        input_fact_ids=(p.id,)))


BUSINESS = Grammar(
    name="business",
    doc="Scenario arithmetic for business claims (compound value).",
    transformations={
        "compound": ParamTransformation(
            "business.compound", apply=_compound,
            param_names=("rate_pct", "years"),
            precondition=lambda inputs: (
                None if inputs.get("principal") is not None
                else "compound needs a principal"),
            doc="FV = PV * (1 + r/100)^years",
            inputs=(InputSpec("principal"),)),
    },
)


def money(value: float, id: str = "?") -> Quantity:
    return Quantity(value=value, unit=Dollar(), id=id)