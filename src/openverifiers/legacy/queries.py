"""OpenVerifiers — Premise and the Query taxonomy.

## Trust model (explicit decision, not a default)

The verifier does NOT re-derive or re-validate facts that were already part of
the premise — they are trusted as given. Verification only checks

  (a) that new facts carry real provenance: a `given=True` marker (set ONLY
      when the fact is declared as a starting input via `Premise.of`) or a
      valid `DerivationRecord` produced by a registered Controller, and

  (b) that the final state satisfies the target Query.

The provenance half (a) is enforced BEFORE the Query runs, recursively over
every fact reachable from the Query's references. An unprovenanced fact —
`given=False` with no derivation, or a derivation pointing at an unregistered
controller/rule — fails verification immediately with a specific reason, no
matter what the Query would otherwise say.

## Query taxonomy

Implemented this sprint:
  FactQuery       — check one fact's value against a target label
  ThresholdQuery  — a fact's value in [min, max] (compliance shape)
  ExistenceQuery  — a fact present AND resolved (status != unknown)
  ConditionQuery  — ConditionController.check output as a Query
  AggregateQuery  — ONE declared target bundling named sub-queries; every
                    sub-check result is reported, none can be silently dropped

Stubbed (interface + intent only, NotImplementedError):
  Invariant, Consistency, Provenance, Completeness, Comparative,
  Counterfactual — see the class docstrings. Out of scope this sprint.

## Query bindings

Every Query references its fact by a TYPED reference: either the actual
Fact instance produced by a controller call (e.g. `deer.position` or the
object returned by `equality_solve(...)`) or an attribute-path label
(e.g. `"deer.position"`, derived automatically from the object graph).
Bare string identifiers are NOT accepted for anything that has a natural
object or controller-call result to reference. The SOLE narrow exception:
scalar facts with no natural owning object (a derived time, a plain
distance) may still be referenced by their label string — this exception
is documented here and nowhere else.

## Verification execution model

No "agent narrates, verifier re-parses text" step. The agent's code runs for
real and produces real typed Fact objects via controller calls; `Specifier.verify`
(after the provenance gate) evaluates the target Query against the actual
Facts in the premise. A `Specifier` is single-use: one premise, one declared
target, one `.verify()` — check-fishing by trying targets until one passes is
not a supported pattern; bundle multiple checks in an `AggregateQuery` instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .facts import (Fact, tag_value, as_number)
from .units import Vector3, to_canonical
from .controllers import REGISTERED_CONTROLLERS
from .conditions import PASS, FAIL, INAPPLICABLE, aggregate

from .constants import REL_TOL


# ---------------------------------------------------------------------------
# Premise
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Premise:
    """Container of given facts and derived facts, each under an explicit
    unique label.

    Construction via `Premise.of(...)`:

        premise = Premise.of(
            facts={"d0": D0, "v": V, "a": A},          # starting inputs
            derived={"catch_time": t_catch, "deer_position": deer_at},
        )

    * every label is unique across BOTH maps; a duplicate raises immediately.
    * facts in `facts=` are forced `given=True` (derivation cleared) — the ONE
      place trust is asserted, per the trust model.
    * facts in `derived=` keep whatever provenance their controller attached;
      an unprovenanced fact there is caught by `Specifier.verify`, not here.
    * the dataclass is frozen and every contained Fact is a frozen pydantic
      model: mutation raises (FrozenInstanceError / ValidationError), so the
      premise cannot be edited after declaration — only replaced.
    """

    facts: tuple[tuple[str, Fact], ...] = ()
    derived: tuple[tuple[str, Fact], ...] = ()

    @classmethod
    def of(cls, facts: Optional[dict[str, Fact]] = None,
           derived: Optional[dict[str, Fact]] = None) -> "Premise":
        seen: set[str] = set()

        def collect(mapping, *, given: bool) -> tuple:
            out = []
            for label, fact in (mapping or {}).items():
                if label in seen:
                    raise ValueError(
                        f"duplicate premise label {label!r} — labels must be "
                        f"unique across facts and derived")
                seen.add(label)
                if given:
                    # the premise boundary is the one place trust is asserted
                    fact = fact.model_copy(update={"given": True,
                                                   "derivation": None})
                out.append((label, fact))
            return tuple(out)

        return cls(facts=collect(facts, given=True),
                   derived=collect(derived, given=False))

    @classmethod
    def of_objects(cls, *objects, given: Optional[dict[str, Fact]] = None,
                   derived: Optional[dict[str, Fact]] = None) -> "Premise":
        """Build a premise from typed objects, not user-chosen strings.

        Every populated fact-typed attribute of each object becomes a given
        fact under its real attribute path (e.g. `"deer.position"`), derived
        generically from the object's model fields — this is NOT physics-
        specific: any object whose fields are Facts works the same way.

        `given=` accepts scalar facts with no natural owning object (e.g. a
        plain distance): the documented fallback, identical to the
        string-keyed `Premise.of` constructor.
        """
        facts = dict(given or {})
        for obj in objects:
            owner_name = getattr(obj, "name", None) or getattr(obj, "id", "?")
            for field in getattr(type(obj), "model_fields", {}):
                value = getattr(obj, field, None)
                if value is None or not isinstance(value, Fact):
                    continue
                label = f"{owner_name}.{field}"
                if label in facts:
                    raise ValueError(
                        f"duplicate premise label {label!r} — attribute paths "
                        f"must stay unique")
                facts[label] = value
        return cls.of(facts=facts, derived=derived)

    # -- lookups --------------------------------------------------------------
    def labels(self) -> tuple[str, ...]:
        return tuple(l for l, _f in self.facts + self.derived)

    def fact(self, label: str) -> Optional[Fact]:
        for l, f in self.facts + self.derived:
            if l == label:
                return f
        return None

    def all_facts(self) -> tuple[Fact, ...]:
        return tuple(f for _l, f in self.facts + self.derived)

    def label_of(self, fact: Fact) -> Optional[str]:
        for l, f in self.facts + self.derived:
            if _same_fact(f, fact):
                return l
        return None

    def facts_with_id(self, fact_id: str) -> list[Fact]:
        return [f for f in self.all_facts() if f.id == fact_id]


def _fact_value(fact: Fact) -> Any:
    return getattr(fact, "value", None)


def is_given(fact: "Fact", frozen_given_ids=None) -> bool:
    """Single given-semantics definition: flagged given, member of a frozen
    zone, or a user-declared raw fact (no derivation). Controller outputs are
    derived, never 'given' unless frozen."""
    if fact.given:
        return True
    if frozen_given_ids is not None and id(fact) in frozen_given_ids:
        return True
    return fact.derivation is None


def _same_fact(a: Fact, b: Fact) -> bool:
    """Provenance-free identity: same type, id, status, value, unit, frame.

    `of_objects` stores model_copy(update={"given": True}) of the caller's
    properties, so instance identity is not preserved across the premise
    boundary — identity is decided on the facts' core content instead."""
    if a is b:
        return True
    if type(a) is not type(b):
        return False
    return (a.id, a.status, a.value, getattr(a, "unit", None),
            getattr(a, "frame", None)) == \
        (b.id, b.status, b.value, getattr(b, "unit", None),
         getattr(b, "frame", None))


def validate_provenance_of(fact: "Fact", find_inputs, seen: set,
                           label: Optional[str] = None,
                           label_for=None,
                           is_given=None) -> Optional[str]:
    """Shared provenance validator (used by Specifier's gate AND the
    VerifierContext graph check — never reimplemented twice).

    `find_inputs(fact_id)` returns the candidate input facts for an id;
    `label_for(input_fact)` gives the label used in nested messages;
    `is_given(fact)` overrides the trust check (default: the fact's own
    `given` flag — the graph passes context-zone semantics, where givens are
    marked by freeze-zone membership, not by the flag). None = trusted."""
    if id(fact) in seen:
        return None
    seen.add(id(fact))
    if fact.given if is_given is None else is_given(fact):
        return None
    rec = fact.derivation
    if rec is None:
        return f"unprovenanced fact: {label or fact.id}"
    controller = REGISTERED_CONTROLLERS.get(rec.controller_name)
    if controller is None:
        return (f"unprovenanced fact: {label or fact.id} — controller "
                f"{rec.controller_name!r} is not registered")
    if rec.rule_name not in controller.rule_names():
        return (f"unprovenanced fact: {label or fact.id} — rule "
                f"{rec.controller_name!r}/{rec.rule_name!r} is not a "
                f"registered rule of that controller")
    for input_id in rec.input_fact_ids:
        candidates = find_inputs(input_id)
        if not candidates:
            return (f"unprovenanced fact: {label or fact.id} — input fact "
                    f"{input_id!r} is not in the premise")
        for cand in candidates:
            sub_label = label_for(cand) if label_for else input_id
            problem = validate_provenance_of(cand, find_inputs, seen,
                                             label=sub_label,
                                             label_for=label_for,
                                             is_given=is_given)
            if problem is not None:
                return problem
    return None


def _resolve(premise: Premise, ref) -> Optional[Fact]:
    """Resolve a query reference: an explicit label string (legacy) or the
    actual Fact instance (attribute-path form)."""
    if isinstance(ref, str):
        return premise.fact(ref)
    for f in premise.all_facts():
        if _same_fact(f, ref):
            return f
    return None


def _ref_display(ref) -> str:
    return ref if isinstance(ref, str) else getattr(ref, "id", "?")


# ---------------------------------------------------------------------------
# Query results
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryResult:
    """One Query's evaluation: verdict + attribution + per-sub results."""

    verdict: str                               # pass | fail | inapplicable
    reason: str = ""
    claims: tuple[str, ...] = ()               # ids of unknown facts involved
    subresults: tuple = ()                     # [(name, verdict, reason)] for aggregates


# ---------------------------------------------------------------------------
# Query base + implemented subtypes
# ---------------------------------------------------------------------------
class Query:
    """A declarative target. `evaluate(premise)` returns a QueryResult."""

    description: str = ""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError

    def referenced_labels(self) -> set[str]:
        """String labels this query references."""
        return set()

    def references(self) -> list:
        """Everything this query targets: label strings (legacy) and/or the
        actual Fact instances (attribute-path form)."""
        return list(self.referenced_labels())


class FactQuery(Query):
    """The referenced fact's value must equal `expected` (within 1e-6
    relative). The reference is a premise label string (legacy) or the actual
    Fact instance (attribute-path form, e.g. `deer.position`)."""

    def __init__(self, label, expected: float, *, description: str = ""):
        self.label = label
        self.expected = expected
        self.description = description or \
            f"FactQuery({_ref_display(label)} == {expected})"
        from .context import note_query
        note_query(self)

    def referenced_labels(self) -> set[str]:
        return {self.label} if isinstance(self.label, str) else set()

    def references(self) -> list:
        return [self.label]

    def evaluate(self, premise: Premise) -> QueryResult:
        fact = _resolve(premise, self.label)
        name = _ref_display(self.label)
        if fact is None:
            return QueryResult(FAIL, f"fact {name!r} is absent from the premise")
        if fact.status == "unknown":
            return QueryResult(INAPPLICABLE, f"{name} is unknown — cannot "
                              f"check the value without guessing",
                               claims=(fact.id,))
        value = _fact_value(fact)
        if value is None:
            return QueryResult(INAPPLICABLE, f"{name} has no value",
                               claims=(fact.id,))
        if isinstance(value, Vector3):
            if not isinstance(self.expected, Vector3):
                return QueryResult(FAIL, f"{name} is a vector; expected a "
                                  f"Vector3 to compare, got "
                                  f"{self.expected!r}")
            comps = ("x", "y", "z")
            if all(
                abs(to_canonical(getattr(value, c), value.unit)
                    - to_canonical(getattr(self.expected, c), self.expected.unit))
                <= REL_TOL * max(1.0, abs(to_canonical(getattr(self.expected, c),
                                                       self.expected.unit)))
                for c in comps) and \
                    value.unit.dimension == self.expected.unit.dimension:
                return QueryResult(PASS, f"{name} == {self.expected}")
            return QueryResult(FAIL, f"{name} == {value}, expected "
                              f"{self.expected}")
        if tag_value(value) != "number":
            return QueryResult(INAPPLICABLE,
                               f"{name} is a {tag_value(value)} value — "
                               f"numeric comparison does not apply",
                               claims=(fact.id,))
        unit = getattr(fact, "unit", None)
        canonical = as_number(value, unit) if unit is not None \
            else float(value)
        if canonical is None:
            return QueryResult(INAPPLICABLE, f"{name} has no numeric value",
                               claims=(fact.id,))
        if abs(canonical - self.expected) <= REL_TOL * max(1.0, abs(self.expected)):
            return QueryResult(PASS, f"{name} == {self.expected} "
                              f"(canonical)")
        return QueryResult(FAIL, f"{name} == {canonical} canonical, expected "
                          f"{self.expected}")


class ThresholdQuery(Query):
    """The labeled fact's value must fall within the declared bounds.

    Compliance shape: loan caps, dosage limits, SLA bounds. Bounds inclusive;
    pass `None` on either side to leave it open. An `unknown` fact is
    `inapplicable`.
    """

    def __init__(self, label, *, min: Optional[float] = None,
                 max: Optional[float] = None, description: str = ""):
        self.label = label
        self.min = min
        self.max = max
        lo = f"{min}" if min is not None else "-inf"
        hi = f"{max}" if max is not None else "+inf"
        self.description = description or \
            f"ThresholdQuery({_ref_display(label)} in [{lo}, {hi}])"
        from .context import note_query
        note_query(self)

    def referenced_labels(self) -> set[str]:
        return {self.label} if isinstance(self.label, str) else set()

    def references(self) -> list:
        return [self.label]

    def evaluate(self, premise: Premise) -> QueryResult:
        fact = _resolve(premise, self.label)
        name = _ref_display(self.label)
        if fact is None:
            return QueryResult(FAIL, f"fact {name!r} is absent from the premise")
        if fact.status == "unknown":
            return QueryResult(INAPPLICABLE, f"{name} is unknown — bounds "
                              f"cannot be checked", claims=(fact.id,))
        value = _fact_value(fact)
        if tag_value(value) != "number":
            return QueryResult(INAPPLICABLE,
                               f"{name} is a {tag_value(value)} value — "
                               f"bounds do not apply",
                               claims=(fact.id,))
        unit = getattr(fact, "unit", None)
        canonical = as_number(value, unit) if unit is not None \
            else float(value)
        if canonical is None:
            return QueryResult(INAPPLICABLE, f"{name} has no numeric value",
                               claims=(fact.id,))
        if self.min is not None and canonical < self.min:
            return QueryResult(FAIL, f"{name} == {canonical} canonical below "
                              f"min {self.min}")
        if self.max is not None and canonical > self.max:
            return QueryResult(FAIL, f"{name} == {canonical} canonical above "
                              f"max {self.max}")
        return QueryResult(PASS, f"{name} == {canonical} canonical within "
                          f"[{self.min}, {self.max}]")


class ExistenceQuery(Query):
    """The labeled fact must be present AND resolved (status != unknown).

    Presence is what matters, not the value — 'was approval obtained at all'.
    Absent -> fail. Present but `unknown` -> inapplicable.
    """

    def __init__(self, label, *, description: str = ""):
        self.label = label
        self.description = description or \
            f"ExistenceQuery({_ref_display(label)} resolved)"
        from .context import note_query
        note_query(self)

    def referenced_labels(self) -> set[str]:
        return {self.label} if isinstance(self.label, str) else set()

    def references(self) -> list:
        return [self.label]

    def evaluate(self, premise: Premise) -> QueryResult:
        fact = _resolve(premise, self.label)
        name = _ref_display(self.label)
        if fact is None:
            return QueryResult(FAIL, f"required fact {name!r} is absent")
        if fact.status == "unknown":
            return QueryResult(INAPPLICABLE, f"{name} is present but "
                              f"unknown — presence cannot be confirmed",
                               claims=(fact.id,))
        return QueryResult(PASS, f"{name} is present and resolved "
                          f"({fact.status})")


class ConditionQuery(Query):
    """Evaluates a ConditionController trace as a query target.

    Interface conformance of ConditionController.check output — same aggregate
    semantics, no behavior change. References no premise labels: its facts are
    the trace's ActionFacts, declared inline.
    """

    def __init__(self, controller, actions, *, description: str = ""):
        self.controller = controller
        self.actions = tuple(actions)
        self.description = description or f"ConditionQuery({controller.name})"
        from .context import note_query
        note_query(self)

    def referenced_labels(self) -> set[str]:
        return set()  # trace facts, not premise facts

    def evaluate(self, premise: Premise) -> QueryResult:
        per_action, claims = self.controller.check_trace(self.actions)
        verdicts = [a["verdict"] for a in per_action]
        overall = aggregate(verdicts) if verdicts else PASS
        claim_ids = tuple(c["reason"] for c in claims)
        if overall == FAIL:
            names = sorted({n for a in per_action
                            for n, v, _r in a["rule_checks"] if v == FAIL})
            return QueryResult(FAIL, "conditions violated: "
                              + ", ".join(sorted(names)), claim_ids)
        if overall == INAPPLICABLE:
            return QueryResult(INAPPLICABLE, "some conditions cannot be "
                              "evaluated (unknown facts)", claim_ids)
        return QueryResult(PASS, f"all {len(per_action)} actions satisfy the "
                          f"conditions", claim_ids)


class AggregateQuery(Query):
    """ONE declared target bundling named sub-queries.

    `Specifier.verify` reports EVERY sub-check's verdict — the caller sees all
    of them and cannot silently discard failures by looping checks externally.
    This is the only supported way to submit multiple checks against one
    premise.
    """

    def __init__(self, subqueries: dict[str, Query], *, description: str = ""):
        self.subqueries = dict(subqueries)
        self.description = description or "AggregateQuery(" + ", ".join(
            sorted(self.subqueries)) + ")"
        from .context import note_query
        note_query(self)

    def referenced_labels(self) -> set[str]:
        out: set[str] = set()
        for q in self.subqueries.values():
            out |= q.referenced_labels()
        return out

    def references(self) -> list:
        out: list = []
        for q in self.subqueries.values():
            out.extend(q.references())
        return out

    def evaluate(self, premise: Premise) -> QueryResult:
        subresults = []
        verdicts = []
        claims: list[str] = []
        for name, sub in self.subqueries.items():
            r = sub.evaluate(premise)
            subresults.append((name, r.verdict, r.reason))
            verdicts.append(r.verdict)
            claims.extend(r.claims)
        overall = aggregate(verdicts) if verdicts else PASS
        failed = [n for n, v, _r in subresults if v == FAIL]
        inapp = [n for n, v, _r in subresults if v == INAPPLICABLE]
        reason = (f"aggregate followup: "
                  f"{len(failed)} failed ({failed}), "
                  f"{len(inapp)} inapplicable ({inapp})") if overall != PASS \
            else "all sub-checks satisfied"
        return QueryResult(overall, reason, tuple(dict.fromkeys(claims)),
                           tuple(subresults))


# ---------------------------------------------------------------------------
# Stubs — taxonomy contract only, deliberately not implemented this sprint
# ---------------------------------------------------------------------------
class InvariantQuery(Query):
    """A property holds across an ENTIRE sequence of steps, not just the
    start/end states."""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("InvariantQuery is stubbed — future work")


class ConsistencyQuery(Query):
    """Two facts or derivations must not contradict (e.g. two independent
    derivations of the same quantity agree within tolerance)."""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("ConsistencyQuery is stubbed — future work")


class ProvenanceQuery(Query):
    """A fact's full derivation ancestry is resolved — zero `unknown` facts
    anywhere in its lineage."""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("ProvenanceQuery is stubbed — future work")


class CompletenessQuery(Query):
    """A checklist-shaped set of required facts is fully present and resolved."""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("CompletenessQuery is stubbed — future work")


class ComparativeQuery(Query):
    """Which of two candidate derivations satisfies a criterion better."""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("ComparativeQuery is stubbed — future work")


class CounterfactualQuery(Query):
    """Does the target still hold if one premise fact is substituted?"""

    def evaluate(self, premise: Premise) -> QueryResult:
        raise NotImplementedError("CounterfactualQuery is stubbed — future work")


# ---------------------------------------------------------------------------
# Specifier + four-part `Verdict`
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Verdict:
    """The four-part output of a Specifier.verify run — never collapsed.

    `reason` and `subchecks` are diagnostics: the reason names the provenance
    failure or aggregate summary; subchecks carry every named sub-result when
    the target was an AggregateQuery.
    """

    target: str
    verdict: str                     # pass | fail | inapplicable
    coverage: tuple[int, int]        # (resolved, declared) premise facts
    unverifiable_claims: tuple[str, ...]
    statistical_residue: None = None       # no LLM-judge layer this sprint
    reason: str = ""
    subchecks: tuple = ()

    def summary(self) -> dict:
        return {
            "target": self.target,
            "verdict": self.verdict,
            "reason": self.reason,
            "coverage_ratio": (self.coverage[0] / self.coverage[1]
                               if self.coverage[1] else None),
            "coverage": {"resolved": self.coverage[0],
                         "declared": self.coverage[1]},
            "unverifiable_claims": list(self.unverifiable_claims),
            "statistical_residue": self.statistical_residue,
            "subchecks": [{"name": n, "verdict": v, "reason": r}
                          for n, v, r in self.subchecks],
        }


@dataclass(frozen=True)
class Specifier:
    """Pairs a Premise with ONE declared target.

        spec = Specifier(premise, AggregateQuery({...}))
        result = spec.verify()

    Single-use: the second `.verify()` call raises. To submit multiple checks,
    bundle them in an AggregateQuery — the premise cannot be re-targeted to
    fish for a passing check.
    """

    premise: Premise
    target: Query
    _used: bool = False

    def verify(self) -> Verdict:
        if self._used:
            raise RuntimeError(
                "Specifier is single-use: one premise, one declared target, "
                "one verify. Bundle further checks in an AggregateQuery."
                "Constructing a second target against the same premise is not "
                "a supported pattern.")
        object.__setattr__(self, "_used", True)

        # -- provenance gate: BEFORE any Query logic runs --------------------
        problem = self._provenance_gate()
        all_facts = self.premise.all_facts()
        resolved = sum(1 for f in all_facts
                       if f.status != "unknown"
                       and getattr(f, "value", None) is not None)
        unknown_ids = [f.id for f in all_facts if f.status == "unknown"]

        if problem is not None:
            return Verdict(
                target=self.target.description,
                verdict=FAIL,
                coverage=(resolved, len(all_facts)),
                unverifiable_claims=tuple(dict.fromkeys(unknown_ids)),
                reason=problem)

        result = self.target.evaluate(self.premise)
        claims = list(result.claims) + unknown_ids
        claims = list(dict.fromkeys(claims))  # dedupe, keep order
        return Verdict(
            target=self.target.description,
            verdict=result.verdict,
            coverage=(resolved, len(all_facts)),
            unverifiable_claims=tuple(claims),
            reason=result.reason,
            subchecks=result.subresults)

    # -- provenance ----------------------------------------------------------
    def _provenance_gate(self) -> Optional[str]:
        seen: set[int] = set()
        for ref in self.target.references():
            fact = _resolve(self.premise, ref)
            if fact is None:
                continue  # query itself reports the absence
            label = self.premise.label_of(fact) or (ref if isinstance(ref, str)
                                                    else str(getattr(fact, "id", "?")))
            problem = validate_provenance_of(
                fact,
                lambda iid: self.premise.facts_with_id(iid),
                seen, label=label,
                label_for=lambda f: self.premise.label_of(f) or f.id)
            if problem is not None:
                return problem
        return None