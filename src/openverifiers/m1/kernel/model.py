"""Kernel data model: facts, requirements, transformations, proofs, verdicts.

Everything here is a frozen dataclass over plain JSON-like values, so a proof
can round-trip through JSON (see ``serialize.py``) and the kernel never
depends on a domain's Python types. Domain meaning is attached only through
the hooks a ``DomainPack`` registers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

FactStatus = Literal["truth", "unverified", "derived", "target", "unknown"]
FACT_STATUSES: tuple[FactStatus, ...] = ("truth", "unverified", "derived", "target", "unknown")

Tier = Literal["hard", "grounded", "soft"]
TIERS: tuple[Tier, ...] = ("hard", "grounded", "soft")

TrustGrade = Literal[
    "fully_hard",  # valid; every step the targets depend on is hard
    "grounded",  # valid; some supporting step is grounded (citation checked), none soft
    "conditional_on_unverified_facts",  # valid only if the listed unverified inputs are true
    "conditional_on_soft_steps",  # valid only if the listed soft (judgment) steps are right
    "undetermined",  # nothing failed, but a target depends on an unknown fact
    "invalid",  # some structural rule, step, or requirement failed
]


@dataclass(frozen=True)
class Provenance:
    """Where a fact came from. ``citation`` names a source id in the domain
    pack's source store; grounded steps must cite one that exists."""

    source: str
    citation: str | None = None


@dataclass(frozen=True)
class Fact:
    """A typed fact. ``type`` must be registered by the domain pack.

    ``status == "unknown"`` is a first-class state: the fact exists but its
    value is not established. It must say ``why_unknown`` and may list the
    ``evidence_needed`` to resolve it. Children are sub-facts with their own
    globally unique ids; they are addressable by id like top-level facts.
    """

    id: str
    type: str
    value: Any = None
    unit: str | None = None
    owner: str | None = None
    status: FactStatus = "truth"
    attributes: Mapping[str, Any] = field(default_factory=dict)
    children: tuple[Fact, ...] = ()
    provenance: Provenance | None = None
    why_unknown: str | None = None
    evidence_needed: tuple[str, ...] = ()


@dataclass(frozen=True)
class Selector:
    """Identifies one fact in the final state.

    Either by ``fact_id``, or by an attribute query: every given key must
    match (``type``, ``owner`` and ``unit`` match the fact's own fields, any
    other key matches ``fact.attributes``). More than one match is an error.
    """

    fact_id: str | None = None
    where: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Requirement:
    """A constraint that must hold on the selected fact after the proof.

    ``predicate`` is a kernel built-in (``exists``, ``equals``) or a name the
    domain pack registers; ``args`` are passed to it.
    """

    id: str
    selector: Selector
    predicate: str = "exists"
    args: Mapping[str, Any] = field(default_factory=dict)


# A hook returns None when satisfied, or a human-readable reason when not.
Inputs = Mapping[str, Fact]
Params = Mapping[str, Any]
PreconditionFn = Callable[[Inputs, Params], str | None]
EffectFn = Callable[[Inputs, Params], Mapping[str, Fact]]
CheckerFn = Callable[[Inputs, Params, Mapping[str, Fact]], str | None]
PredicateFn = Callable[[Fact, Params], str | None]


@dataclass(frozen=True)
class Precondition:
    name: str
    check: PreconditionFn


@dataclass(frozen=True)
class Transformation:
    """A rule ``f(Facts) -> Facts`` registered by a domain pack.

    * ``inputs`` / ``outputs`` map role names to required fact types
      (``"*"`` accepts any registered type).
    * ``effect`` recomputes the outputs from the inputs. When present, the
      kernel compares the proposer's claimed outputs with the recomputed ones.
    * ``checker`` independently checks the step (inputs, params, outputs).
      When there is no effect, the claimed outputs are adopted only if the
      checker accepts them, so every transformation needs at least one hook.
    """

    id: str
    tier: Tier
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    preconditions: tuple[Precondition, ...] = ()
    effect: EffectFn | None = None
    checker: CheckerFn | None = None
    doc: str = ""

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"transformation {self.id!r}: unknown tier {self.tier!r}")
        if self.effect is None and self.checker is None:
            raise ValueError(
                f"transformation {self.id!r} has neither an effect nor a checker, "
                "so nothing could ever check its claimed outputs"
            )
        if not self.outputs:
            raise ValueError(f"transformation {self.id!r} declares no outputs")


@dataclass(frozen=True)
class Step:
    """One application of a transformation. ``inputs`` maps roles to fact ids;
    ``outputs`` maps roles to the facts the proposer *claims* are produced."""

    id: str
    transformation: str
    inputs: Mapping[str, str] = field(default_factory=dict)
    outputs: Mapping[str, Fact] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Proof:
    """Steps in any order; the kernel derives the DAG from fact ids."""

    steps: tuple[Step, ...] = ()


@dataclass(frozen=True)
class FactType:
    """A domain fact type. ``validate`` checks a fact's shape (e.g. value is a
    number, unit parses); ``equal`` decides whether a claimed fact matches a
    recomputed or expected one (default: same value, unit and owner)."""

    name: str
    validate: Callable[[Fact], str | None] | None = None
    equal: Callable[[Fact, Fact], bool] | None = None


@dataclass(frozen=True)
class DomainPack:
    """Everything domain-specific. The kernel only ever reads these fields."""

    name: str
    fact_types: Mapping[str, FactType]
    transformations: Mapping[str, Transformation]
    predicates: Mapping[str, PredicateFn] = field(default_factory=dict)
    sources: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clash = set(self.predicates) & set(BUILTIN_PREDICATES)
        if clash:
            raise ValueError(f"pack {self.name!r} redefines built-in predicates {sorted(clash)}")
        for key, t in self.transformations.items():
            if key != t.id:
                raise ValueError(f"pack {self.name!r}: key {key!r} != transformation id {t.id!r}")
            for role, ftype in {**t.inputs, **t.outputs}.items():
                if ftype != "*" and ftype not in self.fact_types:
                    raise ValueError(
                        f"pack {self.name!r}: {t.id}.{role} uses unregistered type {ftype!r}"
                    )


BUILTIN_PREDICATES: tuple[str, ...] = ("exists", "equals")


@dataclass(frozen=True)
class Failure:
    """A structured reason for rejection.

    ``code`` is stable and machine-readable (see ``FAILURE_CODES``);
    ``facts`` lists the fact ids involved (missing, mismatched, unknown...).
    """

    code: str
    message: str
    step_id: str | None = None
    requirement_id: str | None = None
    precondition: str | None = None
    facts: tuple[str, ...] = ()


FAILURE_CODES: tuple[str, ...] = (
    # structure
    "duplicate_step_id",
    "duplicate_fact_id",
    "unknown_fact_type",
    "invalid_fact",
    "unknown_transformation",
    "missing_input",
    "cycle",
    # steps
    "dependency_failed",
    "input_role_mismatch",
    "output_role_mismatch",
    "input_type_mismatch",
    "input_not_established",
    "input_unknown",
    "precondition_failed",
    "effect_error",
    "output_mismatch",
    "checker_rejected",
    "checker_error",
    "citation_missing",
    # requirements
    "requirement_unmatched",
    "requirement_ambiguous",
    "requirement_unknown",
    "requirement_not_reached",
    "requirement_failed",
    "unknown_predicate",
)


@dataclass(frozen=True)
class TraceEvent:
    """One kernel decision. ``kind`` is structure | step | requirement;
    ``status`` is accepted | rejected | skipped."""

    kind: str
    subject: str
    status: str
    checks: tuple[tuple[str, bool, str], ...] = ()  # (check name, passed, detail)
    failures: tuple[Failure, ...] = ()


@dataclass(frozen=True)
class Verdict:
    valid: bool
    trust_grade: TrustGrade
    failures: tuple[Failure, ...]
    soft_steps: tuple[str, ...]
    unverified_facts: tuple[str, ...]
    support: tuple[str, ...]  # step ids the satisfied requirements depend on
    trace: tuple[TraceEvent, ...]
