"""OpenVerifiers — controllers: the two ways the core produces runnable
`Transformation`s.

Domain-agnostic by construction: nothing in this module knows what any
specific domain's rules mean. `EquationController` solves exactly one declared
equation for exactly one named unknown; `ConditionController` checks exactly
the registered conditions against the given facts. No registry search, no
alternate-path logic, no cycle detection — nothing to search for.

Both expose `as_transformation(...)`, and the engine that runs a Transformation
never needs to know which kind produced it.
"""

from __future__ import annotations

from typing import Any, Optional

from .errors import (SolveError, FrameMismatchError, OwnerMismatchError,
                     RoleMismatchError)
from .facts import Quantity, DerivationRecord

# Registrar: every Controller registers its name here at construction. The
# Specifier's provenance check uses it to confirm a fact's derivation record
# points at a Controller that genuinely exists and really knows the rule.
REGISTERED_CONTROLLERS: dict[str, "Controller"] = {}


class Controller:
    """Base class. Domain code should depend on this, never on the concrete
    kind (same rule as PhysicalObject for object kinds)."""

    name: str


# ---------------------------------------------------------------------------
# EquationController — math/physics domains
# ---------------------------------------------------------------------------
class EquationController(Controller):
    """One symbolic equation, one registration, every solve direction.

        eq = EquationController("v = u + a*t",
                                vars={"v": MeterPerSecond(),
                                      "u": MeterPerSecond(),
                                      "a": MeterPerSecondSquared(),
                                      "t": Second()})
        result = eq.solve_for("t", v=Quantity(...), u=Quantity(...),
                              a=Quantity(...))

    `solve_for` solves EXACTLY this equation for EXACTLY the named unknown:
    every other declared variable must be supplied, any variable not declared
    in the equation is rejected (no search), and dimensional consistency is
    checked on every input.
    """

    def __init__(self, name: str, relation, vars: dict[str, Any], *,
                 shared_owner: bool = False, tolerance: float = 1e-6,
                 role_types: Optional[dict[str, type]] = None):
        # ad-hoc-equation ban: a symbolic relation may only be declared inside
        # the trusted domain library, never in a script or test. The generic
        # composition mechanism (equality_solve) exists for the "find where
        # two trusted outputs coincide" case instead.
        import inspect as _inspect
        caller = _inspect.stack()[1].filename.replace("\\", "/")
        if "/openverifiers/legacy/domains/" not in caller:
            raise RuntimeError(
                f"ad-hoc equations are banned: EquationController "
                f"({name!r}) may only be constructed inside the trusted "
                f"domain library openverifiers/domains/, never in scripts or "
                f"tests. Use equality_solve to compose trusted relations "
                f"instead.")

        from .solvers import solve_quantity
        self.name = name
        self.relation = relation                       # sympy expression == 0
        self.vars = dict(vars)                         # variable -> Unit
        self.shared_owner = shared_owner
        self.tolerance = tolerance
        self._solve = solve_quantity
        self.dims = {var: unit.dimension for var, unit in vars.items()}
        self.role_types = dict(role_types or {})
        REGISTERED_CONTROLLERS[name] = self

    def rule_names(self) -> set[str]:
        return {f"solve_for({var})" for var in self.vars}

    @staticmethod
    def _role_clash(input_fact, role) -> bool:
        """True when a role-typed slot receives a DIFFERENT role-typed fact.
        A plain Quantity passes as a weakly-typed stand-in; a framed wrong
        type (Acceleration into a Velocity slot) is a strong clash."""
        if role is None or input_fact is None or isinstance(input_fact, role):
            return False
        return getattr(input_fact, "frame", None) is not None


    def solve_for(self, target: str, *, frame=None, axis: Optional[int] = None,
                  id: Optional[str] = None, **knowns: Quantity) -> Quantity:
        if target not in self.vars:
            raise SolveError(
                f"{target!r} is not a variable of equation {self.name!r} "
                f"(declared: {sorted(self.vars)}) — no other equation is "
                f"consulted")
        unexpected = set(knowns) - set(self.vars)
        if unexpected:
            raise SolveError(
                f"unknown variable(s) {sorted(unexpected)} for equation "
                f"{self.name!r} — only declared variables may be bound")
        missing = set(self.vars) - ({target} | set(knowns))
        if missing:
            raise SolveError(
                f"can't solve for {target!r}: declared variables without "
                f"known values {sorted(missing)} (exactly one unknown is "
                f"required, no search is performed)")
        if target in knowns and knowns[target] is not None:
            raise SolveError(
                f"target {target!r} already has a known value — nothing to solve")

        validate_call(self, knowns, frame=frame, axis=axis)

        record = DerivationRecord(
            controller_name=self.name,
            rule_name=f"solve_for({target})",
            input_fact_ids=tuple(f.id for f in knowns.values()),
            target=target)
        # provenance produced by a Controller: the result is CONSTRUCTED with
        # the record already attached (single construction), so the context
        # recorder recognizes it as derived at construction time.
        return self._solve(self.relation, target, self.vars[target],
                           knowns, self.dims,
                           shared_owner=self.shared_owner, axis=axis,
                           tolerance=self.tolerance,
                           derivation=record, result_id=id)

    def as_transformation(self, target: str):
        """A plain `Transformation` the engine can run without knowing this
        controller produced it. Pre-bound to one solve direction."""
        from .model import Transformation

        def precheck(inputs: dict) -> Optional[str]:
            try:
                self.solve_for(target, **inputs)
            except Exception as exc:  # noqa: BLE001 — reason becomes the reject
                return str(exc)
            return None

        return Transformation(
            name=f"{self.name}[{target}]",
            apply=lambda inputs: self.solve_for(target, **inputs),
            precondition=precheck,
            doc=self.name,
        )


    # ---------------------------------------------------------------------------
    # Composition — the generic, library-level way to combine trusted relations
    # ---------------------------------------------------------------------------
def validate_call(rel, inputs, *, frame=None, axis: Optional[int] = None) -> None:
    """The five call-site guards shared by solve_for and equality_solve:
    vector-component requirement, role typing, shared-owner consistency,
    reference-frame consistency (within one relation), and the explicit
    frame= kwarg. Raises on the first violation; returns None."""
    vector_inputs = any(hasattr(getattr(f, "value", None), "component")
                        for f in inputs.values() if f is not None)
    if vector_inputs and axis is None:
        raise ValueError("vector inputs require an explicit axis= argument — "
                         "solve one component at a time, never silently")
    role_types = getattr(rel, "role_types", {}) or {}
    for var, f in inputs.items():
        if f is None:
            continue
        role = role_types.get(var)
        if role is not None and rel._role_clash(f, role):
            raise RoleMismatchError(
                f"role mismatch for slot {var!r} of {rel.name!r}: expected "
                f"{role.__name__}, got {type(f).__name__} — role-typed inputs "
                f"cannot be substituted even when dimensions coincide")
    if getattr(rel, "shared_owner", False):
        owners = {f.owner for f in inputs.values()
                  if f is not None and f.owner is not None}
        if len(owners) > 1:
            raise OwnerMismatchError(
                f"owner mismatch in {rel.name!r}: inputs declare different "
                f"owners {sorted(str(o) for o in owners)} — they must share "
                f"one physical object")
    frames = {getattr(f, "frame", None).name for f in inputs.values()
              if getattr(f, "frame", None) is not None}
    if len(frames) > 1:
        raise FrameMismatchError(
            "frame mismatch: inputs belong to different reference frames "
            f"{sorted(frames)} — a relation cannot mix frames")
    if frame is not None:
        for var, f in inputs.items():
            fr = getattr(f, "frame", None)
            if fr is not None and fr != frame:
                raise FrameMismatchError(
                    f"frame mismatch: input {var} is in frame {fr.name!r}, "
                    f"call declares frame {getattr(frame, 'name', frame)!r}")

class CompositionController(Controller):
    """Registry entry for the equality-composition mechanism. Domain-neutral:
    it knows nothing about kinematics or chasing — only that two registered
    relations' outputs can be set equal and solved for a shared unknown."""

    def __init__(self, name: str = "equality_solve"):
        self.name = name

    def rule_names(self) -> set:
        return {"equality_solve"}


COMPOSITION = CompositionController()
REGISTERED_CONTROLLERS[COMPOSITION.name] = COMPOSITION


def equality_solve(rel_a, rel_b, solve_for, *, a_inputs=None, b_inputs=None,
                   axis: Optional[int] = None, frame=None, id: Optional[str] = None):
    """Find where two TRUSTED relations' outputs coincide.

    Composition is NOT a new physical law: it sets rel_a's isolated output
    expression equal to rel_b's and solves for the shared unknown `solve_for`
    (declared by both, unbound in both input sets). Every other variable of
    each relation must be bound in its own input set. Same dimension/frame/
    axis preconditions as any controller call.

    `a_inputs`/`b_inputs` bind each relation's variables separately — the
    two relations may share variable NAMES with different meaning (e.g. a
    different initial velocity 'u' on each side). Returns a Quantity for
    `solve_for` carrying a CompositionController provenance record.
    """
    import sympy as sp
    from .errors import FrameMismatchError, SolveError
    from .facts import DerivationRecord, Quantity
    from .solvers import _scalar_value

    a_inputs = dict(a_inputs or {})
    b_inputs = dict(b_inputs or {})
    if rel_a.name not in REGISTERED_CONTROLLERS or \
            rel_b.name not in REGISTERED_CONTROLLERS:
        raise SolveError("composition requires two REGISTERED, trusted "
                         "relations — unregistered equations cannot be "
                         "composed")
    for label, rel in (("A", rel_a), ("B", rel_b)):
        if solve_for not in rel.vars:
            raise SolveError(f"shared unknown {solve_for!r} is not a variable "
                             f"of relation {rel.name!r} ({label})")
    if solve_for in a_inputs or solve_for in b_inputs:
        raise SolveError(f"shared unknown {solve_for!r} must stay unbound in "
                         f"both input sets")

    knowns = {**a_inputs, **b_inputs}
    vector_inputs = any(hasattr(getattr(f, "value", None), "component")
                        for f in knowns.values() if f is not None)
    if vector_inputs and axis is None:
        raise ValueError("vector inputs require an explicit axis= argument — "
                         "solve one component at a time, never silently")
    frames = {getattr(f, "frame", None).name for f in knowns.values()
              if getattr(f, "frame", None) is not None}
    if len(frames) > 1:
        raise FrameMismatchError(
            "frame mismatch: composed inputs belong to different reference "
            f"frames {sorted(frames)} — a composition cannot mix frames")
    # per-relation guards through the shared validator (vector/role/owner/
    # frame-within-relation + frame kwarg)
    validate_call(rel_a, a_inputs, frame=frame, axis=axis)
    validate_call(rel_b, b_inputs, frame=frame, axis=axis)
    # cross-relation frame consistency on the union
    frames_all = {getattr(f, "frame", None).name for f in knowns.values()
                  if getattr(f, "frame", None) is not None}
    if len(frames_all) > 1:
        raise FrameMismatchError(
            "frame mismatch: composed inputs belong to different reference "
            f"frames {sorted(frames_all)} — a composition cannot mix frames")

    def output_expr(rel, inputs):
        subs = {sp.Symbol(var): sp.sympify(_scalar_value(q, axis))
                for var, q in inputs.items() if q is not None}
        unbound = [v for v in rel.vars if v != solve_for and v not in inputs]
        if len(unbound) != 1:
            raise SolveError(
                f"could not isolate the output of {rel.name!r}: unbound "
                f"variables {unbound} (exactly one, other than "
                f"{solve_for!r}, is required)")
        out = unbound[0]
        roots = sp.solve(rel.relation.subs(subs), sp.Symbol(out))
        if not roots:
            raise SolveError(f"{rel.name!r} has no solution for its output "
                             f"{out!r}")
        return sp.sympify(roots[0])

    e_a = output_expr(rel_a, a_inputs)
    e_b = output_expr(rel_b, b_inputs)
    roots = sp.solve(sp.Eq(e_a, e_b), sp.Symbol(solve_for))
    reals = [float(r.evalf()) for r in roots if r.is_real]
    if not reals:
        raise SolveError("no real coincidence point between the two "
                         "relations")
    positives = [v for v in reals if v > 0]
    val = min(positives) if positives else reals[0]
    val = val / rel_a.vars[solve_for].scale

    return Quantity(id=id or solve_for, value=val,
                    unit=rel_a.vars[solve_for], status="derived",
                    derivation=DerivationRecord(
                        controller_name="equality_solve",
                        rule_name="equality_solve",
                        input_fact_ids=tuple(f.id for f in knowns.values()),
                        target=solve_for))


# ---------------------------------------------------------------------------
# ConditionController — non-math domains (coding now, business/law later)
# ---------------------------------------------------------------------------
class ConditionController(Controller):
    """A named list of conditions, each a Python predicate
    `(performed_trace, proposed_action) -> (verdict, reason)` returning one of
    pass/fail/inapplicable.

    Verdict semantics are the same everywhere in OpenVerifiers:
      pass          the condition holds
      fail          the condition is violated (reason names the fact)
      inapplicable  a referenced fact is explicitly unknown — never coerced

    The controller itself contains no domain knowledge; domains register
    named predicates (see `openverifiers.domains.coding`).
    """

    def __init__(self, name: str, conditions):
        from .conditions import apply_conditions, aggregate
        from .domains.coding import check_trace  # Action-shaped trace driver
        self.name = name
        self.conditions = list(conditions)   # [(name, callable), ...]
        self._apply = apply_conditions
        self._aggregate = aggregate
        self._check_trace = check_trace
        REGISTERED_CONTROLLERS[name] = self

    def rule_names(self) -> set[str]:
        return {c[0] for c in self.conditions}

    def check(self, performed, act):
        """Evaluate every condition against one proposed action."""
        return self._apply(self.conditions, performed, act)

    def check_trace(self, actions):
        """Check a full declared trace in forward order.

        Returns (per_action, inapplicable_claims)."""
        return self._check_trace(actions, self.conditions)

    def as_transformation(self, condition_name: str):
        """Expose one condition as a standard Transformation: its relation
        emits an ActionFact carrying the verdict, so the engine can run
        conditions without knowing the controller kind."""
        from .facts import ActionFact
        from .model import Transformation
        entry = next((c for c in self.conditions if c[0] == condition_name),
                     None)
        if entry is None:
            raise KeyError(f"condition {condition_name!r} not registered")
        name, fn = entry

        def apply(inputs: dict):
            act = inputs["action"]
            performed = inputs.get("performed", ())
            result = fn(performed, act)
            verdict, reason = result if result is not None else ("pass", "")
            return ActionFact(
                id=f"{condition_name}",
                kind="condition_verdict", value=verdict,
                of=str(getattr(act, "seq", None)),
                status="derived",
                # provenance: verdict facts produced inside a Controller carry
                # a record naming which condition produced them.
                derivation=DerivationRecord(
                    controller_name=self.name,
                    rule_name=condition_name,
                    input_fact_ids=tuple(f.id for f in act.pre_facts)))

        def precheck(inputs: dict) -> Optional[str]:
            act = inputs["action"]
            performed = inputs.get("performed", ())
            result = fn(performed, act)
            if result is None:
                return None  # condition does not apply to this action type
            verdict, reason = result
            if verdict == "fail":
                return reason
            if verdict == "inapplicable":
                return f"inapplicable: {reason}"
            return None

        return Transformation(name=f"{self.name}.{condition_name}",
                              apply=apply, precondition=precheck,
                              doc=condition_name)