# Core v1 — Frozen Declaration

Status: **FROZEN.** The two rules below close the design questions formally.
No domain work reopens them. A violation found by a domain is an escalation,
not a redesign: "core gap found in domain X, needs primitive Y" — filed
through the escalation procedure in §4.

Applies to: KDScript-Domain + KDScript-Proof + the compiler, as implemented
in `kerscript/`. Physics (60 relations + 100-problem dataset) is the
vertical validation that froze it.

---

## §1 Rule ONE — Output propagation (owner / frame)

Given a relation `R` with declared typed inputs, and an output typed by a
struct with `owner` and/or `frame` fields:

1. **Frame.** Collect the frames of all BOUND input facts that carry one.
   - 0 frames → output frame = `None` (unframed step in an unframed context).
   - Exactly 1 distinct frame → output frame = that frame.
   - ≥2 distinct frames → **REJECT the step** (no valid common frame;
     relative quantities across frames are undefined). The rejection names
     the conflicting frame facts.
2. **Owner.** Collect the owners of all BOUND input facts that carry one.
   - 0 owners → output owner = `None` (ownerless — e.g. a frame-owned fact).
   - Exactly 1 distinct owner → output owner = that owner.
   - ≥2 distinct owners → output owner = `None` — **explicit ownerless
     rule**: an aggregate/relative quantity has no single owner (e.g.
     relative velocity of two different objects). This is valid, never an
     error; the trace renders the ownerless output distinctly.
3. Guards take precedence: `frame_eq(a,b)`/`different_owner(a,b)` are the
   DECLARED legal filters; the propagation rule is the engine's backstop.
   A step that passes its guards but violates rule 1 is still rejected.
4. Outputs typed without an owner/frame field never acquire one, and never
   cause propagation checks.

## §2 Rule TWO — Guard vocabulary (closed set)

The COMPLETE set of guard kinds v1 may use. `_guard` REJECTS any other
kind at parse time — a domain cannot invent one. Grouped by purpose:

| category | guard | meaning |
|---|---|---|
| existence | `exists(r)` | role MUST be a bound input (never a free solve variable) |
| type | `kind(r, quantity\|action)` | role is that fact kind |
| type | `unit(r, <token>)` | role carries the declared quantity dimension |
| type | `owner_of_type(r, E)` | role's owner is an instance of entity type E (is-a) |
| type | `frame_of_type(r, E)` | role's frame is an instance of entity type E (is-a) |
| owner-consistency | `same_owner(a,b)` | inputs share ONE owner |
| owner-consistency | `different_owner(a,b)` | inputs have DISTINCT owners |
| frame-consistency | `frame_eq(a,b)` | inputs share ONE frame |
| numeric-comparison | `positive(r)` | role's numeric value > 0 |

Plus the implicit type guards AUTO-GENERATED from typed inputs (unit,
owner_of_type, frame_of_type, kind, framed) — they are the same closed
vocabulary, synthesized by the compiler rather than written.

Anything outside this list — proximity, recency, ordering, similarity,
probabilistic — is NOT a v1 guard. Model-backed judgments exist for the
rest.

## §3 Frozen scope

- Keyword discipline: `entity` (object class), `object` (individual),
  `type` (fact SHAPE), `fact` (instance), `relation` (rule),
  `transform`, `judge`.
- `quantity<Unit>` is the ONLY quantity annotation — no per-unit wrapper
  types.
- Entity subtyping via `extends`; polymorphic role acceptance (is-a).
- Assumption/discharge (`assume`, `end`, `end contradiction`) as scoped
  proof boxes over the closed whitelist.
- Judge seam: typed inputs, declared output schema, `judged` provenance
  tier, model backend registry.
- Provenance tiers: `verified | extracted | assumption-dependent | judged`.
- Render projections: success-path / failure-trail / full (below).

## §4 Escalation

A domain that cannot express itself with the frozen primitives files:

    core gap found in domain <X>, needs primitive <Y>

which enters the decision record. It does not edit the core, does not add
a guard, does not fork the compiler. The core changes only by decision.