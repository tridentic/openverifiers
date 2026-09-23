"""OpenVerifiers — typed facts.

`Fact` is the abstract base: identity, verification status, provenance, and an
optional owner. Two concrete subtypes do the real work:

  * `Quantity` — a physics fact. Its `dimension` is *derived* from its typed
    `unit` and can never be stored or set independently. This removes the
    "unit string vs dimension dict disagree" bug class by construction.

  * `ActionFact` — a logic/coding fact (file state, auth flag, ...). No unit,
    no dimension. Real polymorphism: the coding domain is NOT forced through a
    physics-shaped lens.

Canonical construction is always the explicit verbose form:

    Quantity(value=10.0, unit=MeterPerSecond(), owner=PointObject(id="car_1"))

`Quantity.from_str("10 m/s")` is the only sugar — a thin wrapper that parses
the text and returns the exact object the canonical constructor would build.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict

from .units import Unit, Dimension
from .objects import PhysicalObject


# the explicit dimensionless unit (identity scale, empty dimension)
DIMENSIONLESS = Unit(dimension=Dimension())


# ---------------------------------------------------------------------------
# Explicit value tags — comparisons dispatch on a tag, NEVER on Python's
# numeric tower. isinstance(True, int) is True; a discriminated union makes
# such a coercion impossible.
# ---------------------------------------------------------------------------
class NumericValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["number"] = "number"
    value: float


class BooleanValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["boolean"] = "boolean"
    value: bool


class EnumValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["enum"] = "enum"
    value: str
    enum: str


def tag_value(value) -> Literal["none", "number", "boolean", "enum"]:
    """Canonical tagger: checks bool FIRST, so a boolean is never seen as a
    number (bool is not a subclass-friendly proxy here)."""
    if value is None:
        return "none"
    if isinstance(value, BooleanValue):
        return "boolean"
    if isinstance(value, NumericValue):
        return "number"
    if isinstance(value, EnumValue):
        return "enum"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "enum"  # bare strings read as an untyped enum value
    return "none"


def as_number(value, unit: "Unit") -> "float | None":
    """Canonical numeric accessor: returns the SI-canonical float ONLY for a
    number-tagged value, else None (never coerces booleans/strings)."""
    if tag_value(value) != "number":
        return None
    from .units import to_canonical
    return to_canonical(float(value.value if isinstance(value, NumericValue)
                             else value), unit)

Status = Literal["truth", "unverified_truth", "derived", "target", "unknown"]
ProvenanceTier = Literal["verified", "extracted", "assumption-dependent"]


class DerivationRecord(BaseModel):
    """Provenance of a fact produced inside a Controller.

    Set ONLY from Controller internals when they construct a result fact.
    `input_fact_ids` are the ids of the facts that fed the rule (they resolve
    against the premise during the Specifier's provenance walk). Plainly
    inspectable — this is an internal consistency check, not a security
    boundary.
    """

    model_config = ConfigDict(frozen=True)

    controller_name: str
    rule_name: str
    input_fact_ids: tuple[str, ...] = ()
    target: Optional[str] = None

# unit-token registry: populated by application-level modules
# (domains/units_si.py). Core is unit-agnostic — from_str only understands
# tokens a domain has registered.
_UNIT_TOKENS: dict[str, Unit] = {}
_UNIT_DISPLAY: dict[Unit, str] = {}


def register_unit_token(token: str, unit: Unit) -> None:
    _UNIT_TOKENS[token] = unit


def register_unit_display(unit: Unit, token: str) -> None:
    _UNIT_DISPLAY[unit] = token


def unit_display(unit: Unit) -> str:
    return _UNIT_DISPLAY.get(unit, str(unit.dimension))


class Fact(BaseModel):
    # extra="forbid": passing a `dimension=` (or any other stray field) to a
    # Quantity is an error, not an ignored hint — no parallel object shape.
    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_post_init(self, __context) -> None:
        # record into an active VerifierContext, if any (no-op otherwise)
        from .context import note
        note(self)

    id: str = "?"
    status: Status = "truth"
    owner: Optional[PhysicalObject] = None
    source: str = ""
    # provenance contract:
    #   given=True       — set ONLY by Premise.of() when the fact is declared
    #                      as a starting input (the single place trust lives)
    #   given=False      — the fact CLAIMS derivation; then `derivation` MUST
    #                      be a valid DerivationRecord from a Controller, or
    #                      Specifier.verify() rejects it before any Query runs.
    given: bool = False
    derivation: Optional[DerivationRecord] = None
    # Part 3: assumption-scope dependency set (assumption ids this fact relies
    # on). Propagated automatically through DerivationRecord chains.
    dependencies: tuple[str, ...] = ()
    # Part 4: trust tier. "verified" = Transformation-checked (or harness-
    # declared given); "extracted" = LLM-mediated, UNVERIFIED; the effective
    # tier upgrades to "assumption-dependent" whenever dependencies non-empty.
    provenance: ProvenanceTier = "verified"

    @property
    def effective_provenance(self) -> ProvenanceTier:
        if self.dependencies:
            return "assumption-dependent"
        return self.provenance


class QuantifiedFact(Fact):
    """An explicitly quantifier-bearing claim (V/x / E/x), stated before it
    can be proved or used. Not a scope mechanism: it is a Fact type."""

    quantifier: Literal["forall", "exists"]
    variable: str
    value: Optional[EnumValue] = None


class ForAllFact(QuantifiedFact):
    quantifier: Literal["forall"] = "forall"


class ExistsFact(QuantifiedFact):
    quantifier: Literal["exists"] = "exists"


class ImplicationFact(Fact):
    """A discharged conditional — produced ONLY by assumption-scope closure
    (P3). `premise` is the discharged assumption's claim text, `conclusion`
    the id of the scope's terminal fact."""

    premise: str
    conclusion: str


class ExpressionFact(Fact):
    """A symbolic expression from one syllabus relation, with free variables
    still unbound. Produced by a primitive in expression mode; composed and
    closed by algebra.equate (or a later numeric primitive call). Carries the
    output variable's unit so the closed result becomes a Quantity."""

    expression: str
    variables: tuple[str, ...] = ()
    unit: Unit


class Quantity(Fact):
    """A physics fact: value + typed unit (+ optional owner).

    `value` is `None` ONLY when `status == "unknown"` — the verifier never
    coerces an unknown to a number (that is a hard rule of this codebase).
    """

    value: Optional[float] = None
    unit: Unit

    @property
    def dimension(self):
        """Derived, never stored: the unit is the single source of truth."""
        return self.unit.dimension

    def __str__(self) -> str:
        return f"{self.value} {unit_display(self.unit)}".strip()

    @classmethod
    def from_str(cls, text: str, *, id: str = "?", status: Status = "truth",
                 owner: Optional[PhysicalObject] = None) -> "Quantity":
        """Sugar macro: parse `"10 m/s"` into the canonical verbose form.

        Thin wrapper ONLY — it builds exactly what
        `Quantity(value=..., unit=..., ...)` would build, with the same
        validation. It must never produce an object the canonical constructor
        could not have produced.
        """
        parts = text.split(None, 1)
        if len(parts) == 2 and parts[1] in _UNIT_TOKENS:
            return cls(value=float(parts[0]), unit=_UNIT_TOKENS[parts[1]],
                       id=id, status=status, owner=owner)
        if len(parts) == 1:
            return cls(value=float(parts[0]), unit=DIMENSIONLESS,
                       id=id, status=status, owner=owner)
        raise ValueError(f"cannot parse quantity text {text!r}; unknown unit "
                         f"{parts[1]!r}")


class ActionFact(Fact):
    """A logic-domain fact (coding today, business/law/ethics later).
    Deliberately unit-less."""

    kind: str
    value: Any
    of: Optional[str] = None  # binding target, e.g. the record a fact refers to
    expr: str = ""           # math proof slice: the closed-form expression a
                             # proposition/implication is declared with