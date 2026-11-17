"""OpenVerifiers — core model: the Transformation seam and VerificationResult.

The typed facts live in `facts.py` (Fact / Quantity / ActionFact) and are
re-exported here. `Transformation` is the one seam both controller kinds
produce and the engine consumes — the engine never needs to know which kind
produced a given Transformation, which is what keeps adding a new domain a
zero-core-change operation.

`Transformation` supports two construction modes, explicitly:

  1. SUBCLASS MODE (preferred) — a real type hierarchy. A class overrides
     `apply(self, inputs)` (and optionally `apply_step(self, inputs,
     params)` on the ParamTransformation branch), carries its declared
     `inputs` spec, and can hold state. Polymorphism is exercised: the
     runner calls `.apply` through the base interface, exactly like
     Quantity/owner/frame dispatch in the typed core.
  2. FUNCTIONAL MODE — a small adapter for trivial grammars
     (Transformation(name, apply=fn, precondition=fn)). Kept for simple
     cases, but a Transformation is never *just* closure pointers: the
     declared input spec and the apply contract live on the class.
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from dataclasses import dataclass

from .facts import Fact  # noqa: F401  (re-exported)


@dataclass(frozen=True)
class InputSpec:
    """One declared input of a Transformation.

    `name` is the role the DSL/trace must supply; `type` is the required
    Fact kind (default: any Fact). `required=False` marks a variable that
    may be LEFT FREE — needed for primitives that solve for an unbound
    variable, or emit a symbolic expression when two variables stay free
    (later composed by algebra.equate).
    """

    name: str
    type: type = Fact
    required: bool = True


class Transformation:
    """A runnable verification step.

    produced by EquationController, ConditionController, or anything else:

        inputs  -> tuple[InputSpec, ...]      (declared signature)
        apply(inputs)        -> Fact
        precond(inputs)      -> None | reason-string

    `inputs` is a dict[str, Fact] keyed by role. Subclass mode overrides
    `apply`; functional mode supplies it as `apply=` at construction.
    """

    def __init__(self, name: Optional[str] = None, *,
                 apply: Optional[Callable[[dict], Fact]] = None,
                 precondition: Optional[Callable[[dict], Optional[str]]] = None,
                 doc: str = "",
                 inputs: tuple[InputSpec, ...] = ()):
        self.name = name or type(self).__name__
        self.doc = doc
        self.inputs = inputs
        self._apply_fn = apply
        self._pre = precondition

    def apply(self, inputs: dict) -> Fact:
        """Execute the step. Subclasses override this; the functional adapter
        delegates to its closure. `inputs` has been signature-validated and
        resolved by the runner before this is reached."""
        if self._apply_fn is None:
            raise NotImplementedError(
                f"{type(self).__name__} must implement apply() — a "
                f"Transformation is not a bare struct of closures")
        return self._apply_fn(inputs)

    def precond(self, inputs: dict) -> Optional[str]:
        return self._pre(inputs) if self._pre else None

    def required_inputs(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.inputs)

    def describe(self) -> str:
        return self.name


class ParamTransformation(Transformation):
    """Transformation whose apply additionally receives validated step params.
    Subclasses override `apply_step(inputs, params)`; functional mode supplies
    `apply=` accepting (inputs, params)."""

    def __init__(self, name: Optional[str] = None, *,
                 apply: Optional[Callable[[dict, dict], Fact]] = None,
                 precondition: Optional[Callable[[dict], Optional[str]]] = None,
                 param_names: tuple[str, ...] = (),
                 doc: str = "",
                 inputs: tuple[InputSpec, ...] = ()):
        super().__init__(name, apply=None, precondition=precondition,
                         doc=doc, inputs=inputs)
        self._apply_p = apply
        self._param_names = param_names

    def apply(self, inputs: dict, params: Optional[dict] = None) -> Fact:  # type: ignore[override]
        if self._apply_p is not None:
            return self._apply_p(inputs, params or {})
        raise NotImplementedError(
            f"{type(self).__name__} must implement apply(inputs, params)")

    def apply_step(self, inputs: dict, params: dict) -> Fact:
        return self.apply(inputs, params)

    def validate_params(self, params: dict) -> Optional[str]:
        for k in params:
            if self._param_names and k not in self._param_names:
                return f"unexpected param {k!r} (allowed: {self._param_names})"
        return None


class VerificationResult:
    """Outcome of an Engine.run: verdict + JSON-auditable trace."""

    def __init__(self, target: str, status: str, answer: Any, trace: list[dict]):
        self.target = target
        self.status = status          # "RESOLVED" | "UNRESOLVED"
        self.answer = answer          # Fact | None
        self.trace = trace            # list of trace events (JSON-serializable)

    def summary(self) -> dict:
        return {"target": self.target, "status": self.status,
                "answer": None if self.answer is None else str(self.answer),
                "trace_len": len(self.trace)}