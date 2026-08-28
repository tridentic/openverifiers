"""OpenVerifiers — core model: facts, transformations, unknowns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------
TRUTH = "truth"
UNVERIFIED_TRUTH = "unverified_truth"
DERIVED = "derived"
TARGET = "target"
UNKNOWN = "unknown"

ALL_STATUSES = (
    TRUTH,
    UNVERIFIED_TRUTH,
    DERIVED,
    TARGET,
    UNKNOWN,
)


# ---------------------------------------------------------------------------
# Fact
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Fact:
    """A single atomic piece of information.

    Identity is `id`. Two facts with the same id are the same fact — this is the
    DAG deduplication key (see engine). Facts are frozen; derivation creates new
    facts rather than mutating.
    """

    id: str
    value: Any
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    derivation: Optional[str] = None  # transformation name that produced this

    def __post_init__(self) -> None:
        if self.status not in ALL_STATUSES:
            raise ValueError(f"invalid status {self.status!r}; expected one of {ALL_STATUSES}")


# ---------------------------------------------------------------------------
# Transformation / rule
# ---------------------------------------------------------------------------
class Transformation:
    """A known rule: input facts -> output fact, gated by a precondition.

    - precondition(inputs) -> str | None
        Return None if the rule may fire, else a non-empty reason string why not
        (dimension mismatch, missing fact kind, ...). The reason is recorded in
        the trace — rejected applications are auditable.
    - relation(inputs) -> (output_fact, trace_note)
        Compute the output fact from the inputs (or delegate to a solver hook).
    - solver_hook: backend token ('sympy.algebra', ...). Kept as metadata; the
        engine dispatches to the solver layer.
    """

    def __init__(self, name, *, output_kind: str, input_kinds: list=None, precondition=None,
                 relation=None, solver_hook: str = "", doc: str = ""):
        self.name = name
        self.output_kind = output_kind
        self.input_kinds: list[str] = input_kinds if input_kinds is not None else []
        self.precondition = precondition if precondition is not None else self._default_precondition
        self.relation = relation
        self.solver_hook = solver_hook
        self.doc = doc

    @staticmethod
    def _default_precondition(_inputs):
        return None

    def precond(self, inputs: list[Fact]) -> Optional[str]:
        """Return None = allowed; non-None = rejection reason (recorded)."""
        return self.precondition(inputs)

    def apply(self, inputs: list[Fact]) -> tuple[Fact, str]:
        """Run relation + solver to produce the output fact.

        Returns (fact, note). Expects precondition already passed."""
        if self.relation is None:
            raise RuntimeError(f"transformation {self.name} has no relation")
        fact, note = self.relation(inputs)
        return fact, note

    def describe(self) -> str:
        return f"{self.name} ({self.output_kind})"


# ---------------------------------------------------------------------------
# Unknown
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Unknown:
    """A first-class 'cannot determine' fact — not a failure state.

    reason: why it is unknown (missing given, out of coverage, ...).
    evidence_needed: what would resolve it (an input fact, a rule, ...).
    """

    id: str
    reason: str
    evidence_needed: str = ""

    def to_fact(self) -> Fact:
        return Fact(
            id=self.id,
            value=None,
            status=UNKNOWN,
            attributes={},
            source="unknown",
            derivation=None,
        )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class VerificationResult:
    """Outcome of a verify() run: verdict + trace views."""

    target: str
    status: str  # 'RESOLVED' | 'UNRESOLVED' | 'UNKNOWN'
    answer: Any
    success_path: list  # list of trace events (see trace.py)
    failure_trail: list
    full: list

    def render(self, view: str = "success-path") -> str:
        from .trace import render_view
        return render_view(view, self)

    def summary(self) -> dict:
        return {
            "target": self.target,
            "status": self.status,
            "answer": str(self.answer),
            "success_path_len": len(self.success_path),
            "failure_trail_len": len(self.failure_trail),
            "full_len": len(self.full),
        }