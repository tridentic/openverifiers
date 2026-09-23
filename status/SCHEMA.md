# Status Database — Schema and Operation Taxonomy

This is the canonical, machine-readable record of where OpenVerifiers stands:
what we target, what logic each domain grammar covers, what is shipped versus
designed versus out-of-scope, and which operations each grammar supports.

Every domain lives as one `<family>.json` under `status/`. `index.json` is the
registry. Grammar source of truth is a **Python module** in `grammars/` — there
is no `.ovpl` source-of-truth; `spec/ovpl/proof.ovpl` is a superseded design sketch.

The playground (future) will ingest these files directly. Treat every field as
contract.

---

## 1. Files

| Path | Purpose |
|---|---|
| `db.json` | Top-level registry: version, target, timeline, cross-cutting status, decision log |
| `domains.json` | The full roadmap catalog — every domain the core model makes possible, bucketed by deployed status (shipped / in progress / researching / next-up / near-term / exploratory / flagship). Superset of the marketing site; the future playground's index. |
| `<family>.json` | One per shipped-or-designed discipline family (physics, operations, normative), with grammar, operations, evidence, decisions, gaps |
| `DX.md` | The pythonic polymorphic grammar-authoring contract — facts/transformations as typed classes, nesting, polymorphism, the proof footprint, and derived-fact persistence + invalidation (the OpenWiki move). Accepted direction; engine migration staged over SDLC so the shipped physics slice stays green. |
| `examples.json` | Canonical, real end-to-end engine output for 10 domains (sympy + z3). Every verdict is a LIVE run, never hardcoded. Regenerated via grammars/examples.py run_all(). |
| `SCHEMA.md` | This document — the invariant every file must satisfy |

## 2. Domain family grouping

Domains are grouped by discipline family (not one-file-per-grammar) because the
families are the AO-narrative units and each shares verification idioms:

| Family | Domains | Shared concern |
|---|---|---|
| `physics` | kinematics, mechanics | unit/dimensional analysis, equations over reals |
| `operations` | logistics, finance, planning | discrete constraints (enums, dates, money), satisfiability |
| `normative` | law, code-contracts | typed rules, preconditions, compliance |

`index.json` may add families as grammars ship.

## 3. Operation taxonomy

Each operation is a **concrete engine behavior with a defined input/output
contract** — not a vague label. An operation appears in a domain only if it is
(1) shipped in code, or (2) a genuinely required next capability with a worked
input/output contract. No filler.

### Shipped operations (implemented, tested)

| op | signature | behavior | evidence |
|---|---|---|---|
| `derive` | `given: Fact[] → target: target(Fact)` | backward deduction: fire transformations toward a `target` fact → `RESOLVED(answer)` or `UNKNOWN` | `Engine.deduce`, `verify_fixture`; 20/20 benchmark |
| `verify` | `given: Fact[] → candidate: value` | derive target, compare `RESOLVED` answer to candidate within `1e-6` relative tolerance → pass/fail + divergence note | benchmark runner; `RESULTS.md` |
| `induce` | `given: Fact[] → fixed-point` | forward closure: fire every applicable rule until no new fact | `Engine.induce` (shipped, lightly tested) |
| `unknown` | `reason, evidence_needed → UNKNOWN` | first-class "cannot determine" verdict, distinct from proven-wrong | `Unknown`, `ev_unknown` |

### Required next operations (designed, not built)

Only these are admitted. Each is concrete and load-bearing.

| op | contract | why it must exist |
|---|---|---|
| `conflicts` | `claim: Fact[] → minimal violated rule subset` | the unsat-core "why not" — returns the smallest rule set blocking a claim, for self-repair feedback. Needs Z3 backend. |
| `precond_throw` | `transformation attempt with missing satisfiability input → raise` | the "no satisfied→error" compiler semantics: missing precondition throws, not soft-unknown. |
| `frontier` | `state: Fact[] → legal transformations` | action-space gating: given current state + rules, which steps are provable legal. The "mountain ascent" surface. |

No other operations are adopted until a worked, concrete example exists in this
document and a decision records acceptance.

## 4. Domain record schema

```json
{
  "id": "physics",
  "family": "physics",
  "title": "Physics (kinematics + mechanics)",
  "status": "shipped",                 // shipped | designed | stub | out-of-scope
  "grammar": {
    "module": "grammars/physics.py",
    "kind_meta": "KIND_META",
    "rules_fn": "build_physics_rules"
  },
  "why_verify": "...",                  // problem statement
  "how_handled_now": "...",             // current practice this replaces
  "logic": {
    "fact_kinds": ["initial_velocity", ...],
    "transformations": [{"name":"v = u + a*t","inputs":[...],"output":"final_velocity","solver":"sympy.algebra"}],
    "roots": ["F = m*a is definitional"]
  },
  "operations": {
    "shipped": ["derive","verify"],
    "designed": ["conflicts","precond_throw"],
    "out_of_scope": ["statistical_semantics"]
  },
  "scenarios": [
    {
      "id": "phys-01",
      "plain": "A car accelerates...",
      "given": [{"kind":"initial_velocity","value":"10 m/s"}, ...],
      "target": {"kind":"displacement"},
      "operation": {"type":"derive"},
      "expected": {"value": 300, "unit": "m"}
    }
  ],
  "evidence": {
    "benchmark": {"file":"RESULTS.md","passed":20,"total":20,"date":"..."},
    "verified": [{"by":"openwiki/0.4.3","at":"2026-08-28T20:01:59Z"}]
  },
  "decisions": [
    {"id":"dec-01","date":"...","decision":"...","rationale":"...", "status":"final"}
  ],
  "out_of_scope": [
    {"claim":"statistical semantics (tone, style)","why":"</reason>"}
  ]
}
```

## 5. Invariants

1. `status` is exactly one of `shipped | designed | stub | out-of-scope`.
2. `grammar.module` is the single source of truth for rules — never a `.ovpl` file.
3. `operations.designed` is empty unless the operation has a contract row in §3.
4. `decisions` is chronological; each entry is `final | superseded | open`.
5. `out_of_scope` is declared explicitly — an unclaimed ability is a gap, not a feature.

## 7. Grammar-authoring DX (pythonic polymorphism)

The accepted authoring surface is *Python classes*, not string tokens / dict configs.
See `DX.md` for the full contract. Schema implications for `domains.json`:

- Each `verifiable_because` must state the **typed class surface** the domain needs
  (a quantity kind, a graph of resource facts, an obligation class, ...).
- `framework_lesson` is where a domain's need for a new class shape, polymorphism,
  or nesting is recorded.

Invariant 2 is read *with* this in mind: `grammar.module` is the source of truth,
and in class-DX the module *is* the typed grammar — classes, not `make_rule`.

## 8. Derived-fact persistence + invalidation

Accepted direction: proved facts persist across runs, each **linked back to the
source content it was derived from** (code, physics setup, source doc). A
`source_version` bump invalidates every persisted fact whose transitive footprint
touches that source; the stale subgraph re-derives, and downstream conclusions
recompute. This is incremental proof — a physical sandbox that implements this
system is logic-ready from day one. It is a caching layer over the acyclic proof
store and cannot introduce circular reasoning (the DAG prohibition holds).

Persistence-relevant domains should note it in their `framework_lesson` (e.g.
physics/sandbox, code-refactor, data-pipeline — all source-editable).