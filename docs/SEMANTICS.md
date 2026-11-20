# OpenVerifiers v1 semantics

This file defines what the RawOV kernel computes, which verdicts follow, and
why the checker's acceptance of a trace makes those verdicts sound. It covers
Milestone 0: RawOV, labels, verdicts, stratified negation and budgets.
Plugins (M2) and OKQL (M4) will extend it.

## 1. Programs

A RawOV program has four parts:

- **World policies:** `world p open|closed`. Open is the default.
- **Ground facts.** Each fact has an origin: `axiom:`, `fact:`, `import:`,
  `domain:` or `assume:<name>`.
- **Finite domains.** `domain d: pred(args) = {v1, …} complete|partial` stands
  for the facts `pred(args, vi)`.
- **Rules.** `head :- l1, …, ln`. A body literal is one of:
  - a positive atom `p(t̄)` or `neg p(t̄)`. The strong negation `neg p` is a
    separate relation, written `neg p`;
  - `not a`;
  - `X is e`;
  - a comparison `e1 op e2`.

Terms are symbols, strings, exact rational quantities with a dimension vector,
variables, and compound terms.

**Well-formedness** (`raw.validate`):
- ids are unique and facts are ground;
- rules are safe when read left to right. Positive literals bind variables;
  `not`, `is` and comparisons only read variables that are already bound;
  `is` binds a fresh variable; every head variable is bound.

**World policy rewrite** (`effective_body`):
- For an *open* predicate p, `not p(t̄)` means `neg p(t̄)` is derived.
  Not-derived is not enough. The literal is rewritten to the positive literal
  `neg p(t̄)`, and `not neg p(t̄)` to `p(t̄)`.
- Only closed-world `not` remains as negation-as-failure.

**Stratification.** An assignment `s` from predicate keys to ℕ must satisfy:
- `s(head) ≥ s(b)` for every positive body key `b`;
- `s(head) > s(b)` for every closed-world `not b`.

Programs without such an assignment are rejected with the offending cycle
(`NotStratifiable`).

## 2. Labels

**Assumptions.** `A` is the set of names in `assume:` origins.

**Literals and environments.** A literal is `a` (assumption a is active) or
`¬a` (it is not). An environment `e` is a consistent finite set of literals.

**Satisfaction.** A context `C ⊆ A` is the set of active assumptions. It
satisfies `e` when `pos(e) ⊆ C` and `neg(e) ∩ C = ∅`.

**Labels.** A label is an antichain of environments under ⊆, with no
inconsistent members. `L` holds in C when some `e ∈ L` is satisfied by C.
- Facts with any origin other than `assume:` have the label `TRUE = {∅}`.
- `assume a` has the label `{{a}}`.
- `FALSE = {}`.

**Operations.** Write `min` for removing inconsistent environments and
supersets.

| operation | definition | meaning |
|---|---|---|
| conjunction | `L1 ⊗ L2 = min{e1 ∪ e2}` | holds where both hold |
| disjunction | `L1 ⊕ L2 = min(L1 ∪ L2)` | holds where either holds |
| negation | `¬L = min{ {flip(ℓ_e) : e ∈ L} : ℓ_e ∈ e }`: the minimal hitting sets with every literal flipped | holds in C exactly when L does not (property-tested) |

**Labelled least model.** Evaluate stratum by stratum. Within a stratum, take
the least fixpoint of

    label(h) ⊇ label(b1) ⊗ … ⊗ label(bk) ⊗ ¬label(c1) ⊗ … ⊗ ¬label(cm)

over every ground rule instance `h :- b1..bk, not c1..cm, builtins` whose
builtins hold. Here `label(c)` is the final label of c from a lower stratum.

Because negation uses exact labels from completed lower strata, the result
satisfies the following.

> **Context independence.** For every C ⊆ A and atom p, label(p) holds in C
> iff p is in the stratified model of the program whose `assume:` facts are
> restricted to C.

So changing the active assumptions (`WHAT IF ASSUME/RETRACT <assumption>`) is
a label lookup. `tests/v1/test_kernel.py::test_what_if_by_label_lookup_equals_rerun`
checks this against a full re-run on random programs.

**Nogoods.** `N = min{e1 ∪ e2 : e1 ∈ label(p), e2 ∈ label(neg p)}`. These are
the environments in which a contradiction holds.

## 3. Verdicts

For a ground query `q` and context C, by default C = A:

1. `INCONSISTENT(conflict_set)` if C satisfies some n ∈ N. The conflict set is
   the facts (and assumptions) used in the derivations of `p` and `neg p` for
   that nogood. If n = ∅, the base theory itself is inconsistent.
2. `PROVEN(proof, e)` if C satisfies some e ∈ label(q). The proof is the set of
   trace steps of one derivation valid under e.
3. `REFUTED(proof, e)` if C satisfies some e ∈ label(neg q). It is also
   REFUTED with `closed_world` set if q's predicate is closed, its stratum is
   complete, and q is not PROVEN; then e ∈ ¬label(q) is satisfied by C.
4. `UNKNOWN(missing, reason)` otherwise, where reason is:
   - `budget` if q's or neg q's stratum is incomplete or a label was truncated;
   - `missing_facts` if q holds under other contexts, in which case `missing`
     lists the assume/retract changes needed. It is also `missing_facts` if
     the (untrusted) frontier search names premises a derivation is stuck on;
   - `open_world` otherwise.

Confidence and source metadata never enter labels or verdicts.

## 4. Traces and the checker

The evaluator emits a trace: an ordered list of steps. A fired step records:
- the fact or rule id and its substitution;
- the premise step ids;
- for each closed `not c`, a reference to c's final step (or "absent");
- `prev`, the conclusion's previous step;
- the conclusion's *cumulative* label after the firing.

The checker accepts the trace only if all of the following hold.

1. **Valid strata.** The program is well-formed and the claimed strata satisfy
   §1.
2. **Local justification**, step by step in order:
   - the instantiated head equals the conclusion, and each instantiated body
     atom equals its premise's conclusion;
   - premises occur earlier in the trace;
   - builtins hold;
   - `label = min(label(prev) ∪ ⊗(premise labels, ¬final labels))`.
3. **Negation.** Each negation reference names the final step of that atom,
   in a stratum that is complete.
4. **Closure.** For every stratum claimed complete, with all lower strata
   complete and no truncated label: every rule instance over the final model
   yields an environment set already covered by the head's label, and every
   fact is present.

**Soundness sketch.**

- **Claimed environments are entailed.** By induction on trace position,
  every environment in every step label is entailed: it is a union of premise
  environments that are entailed by earlier steps, and earlier-only references
  make the induction well-founded. Negation references use final labels of
  complete lower strata, so by the inductive hypothesis for those strata they
  are exact.
- **Complete strata are exactly the least model.** Closure says the claimed
  labels are a pre-fixpoint, so they contain the least labelled model. Local
  justification says they are contained in it.
- **Verdicts follow.**
  - PROVEN and neg-REFUTED rest only on entailed environments.
  - Closed-world REFUTED rests on exactness of a complete stratum.
  - INCONSISTENT rests on entailed environments of p and neg p.
  - Nothing else is asserted; everything else is UNKNOWN.

**Mutation evidence.** `tests/v1/test_checker.py` corrupts real traces in nine
ways: wrong substitution, missing or swapped premise, swapped or weakened
label, wrong or negated conclusion, wrong `prev`, wrong negation reference,
dropped step, fabricated fact. The checker rejects every non-equivalent mutant
of complete traces, and no mutant of any trace changes a verdict.
- Dropping a step from a stratum that is *already incomplete* can be accepted.
  The result is a smaller but still sound model, which can only turn answers
  into `UNKNOWN(budget)`. Such mutants are counted separately as "weakened".

## 5. Budgets

- **Limits:** steps, atoms, term depth, label size and wall time.
- **Cut-off.** Exceeding any of them marks the current stratum incomplete, and
  evaluation stops there. Positive results already derived stay sound.
- **Truncation.** A label over the size cap keeps only its smallest
  environments; the atom is marked truncated and its stratum becomes
  incomplete.
- **Partial domains.** A `partial` domain makes its predicate's stratum
  incomplete from the start.
