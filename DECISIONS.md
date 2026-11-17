# Decisions

One line of reasoning per decision. Newest sections at the bottom.

## Reconciling the pre-M1 code (Milestone 1 start)

What existed: a pydantic typed core (`Fact`/`Quantity` with SI dimension
algebra), a *linear* trace runner (`v2.run_trace`) over a name-whitelisted
`Registry` of `Grammar`s, a line DSL, `Query`/`Specifier` targets with a
provenance gate, ~60 physics relations, small math/law/business/english/coding
slices, a Claude Code PreToolUse gate, and 202 passing tests. KDScript (the
grammar DSL) lives only on the `kdscript` branch.

- **Moved all of it to `openverifiers/legacy/`, unchanged except imports.** Nothing working is deleted; its 202 tests still run in `tests/legacy/`.
- **Fixed the package layout.** The repo root *was* the package, so `pip install -e .` shipped nothing and tests only ran from the parent directory.
- **New kernel instead of refactoring `v2.run_trace`.** It is linear, stops at the first failure, has no DAG/cycle check, no tiers, no claim-vs-recompute comparison, and `submit()` imports `domains` (kernel → domain). Fixing all of that rewrites it anyway.
- **Kernel uses stdlib dataclasses, not pydantic.** Keeps the trusted base dependency-free and makes `mypy --strict` straightforward; JSON parsing is a small strict hand-written layer.
- **No global side effects in the kernel.** Legacy `Fact.model_post_init` writes into a global context on every construction; the kernel is a pure function.
- **Ported ideas, not code:** name-whitelisted dispatch (pack registry), "hook exceptions fail closed", "unknown never silently passes", "one equation registration gives every solve direction" (legacy `EquationController` → math pack formulas), and SI dimension vectors (math pack).
- **KDScript and the line DSL are not used.** Proofs are JSON in M1; grammar extraction is a non-goal. The `kdscript` branch is untouched.
- **Legacy pyflakes test now runs `ruff --select F`.** pyflakes was only present in a global conda env; ruff is already a dev dependency.
- **pydantic is an optional `legacy` extra** (included in `dev`), so the core install is `sympy` + `z3-solver`.
- **`requires-python >= 3.11`** as requested (legacy said 3.12). Developed and tested locally on 3.12 only; CI matrix covers 3.11-3.13.

## Kernel

- **Proof = unordered steps; the DAG comes from fact ids.** A step depends on the step producing each input id. The proposer's step order is irrelevant (tested by a hypothesis shuffle test).
- **The kernel keeps going after a failure.** Every step is reported: rejected, accepted, or skipped (`dependency_failed`). That is what makes `failure_trail` useful as repair feedback.
- **Effect and checker are separate hooks; at least one is required.** With an effect, claimed outputs must equal the recomputation, and the *recomputed* facts enter the state. Without one (code changes, LLM judgments), claims are adopted only if the checker accepts them.
- **Output ids may fill an initial `target` or `unknown` slot, nothing else.** Re-defining an established fact is `duplicate_fact_id`.
- **Steps cannot consume `target` or `unknown` facts.** Unknown inputs produce `input_unknown` carrying `evidence_needed`.
- **`undetermined` grade:** not valid, but every failure traces to an unknown fact rather than a wrong claim. Distinguishes "can't tell yet" from "wrong".
- **Trust grade only looks at the support set** (steps the satisfied requirements transitively depend on). A soft step that nothing relies on does not taint the result. Any failure anywhere still makes the proof invalid.
- **Grade order: soft > unverified inputs > grounded > hard.** `conditional_on_unverified_facts` was added because `unverified` initial facts are as much an assumption as a soft step.
- **Grounded tier: the kernel checks the citation exists in `pack.sources`; the pack checker checks the content.** Existence is domain-agnostic; whether the text supports the claim is not.
- **Equality is pack-defined per fact type** (`FactType.equal`), default: same type/unit/owner and values `isclose(rel=1e-9, abs=1e-12)`. The math pack needs unit conversion; the kernel shouldn't know about units.
- **Built-in predicates are only `exists` and `equals`;** packs add the rest and cannot shadow built-ins.
- **Attribute selectors also match `type`, `owner`, `unit`.** More than one match is `requirement_ambiguous` (a failure in the verdict, not a Python exception, so it appears in the trace).
- **Initial facts may not claim `derived`.** Derived status is only ever assigned by the kernel.
- **Children are flattened into the fact index** so they are deduplicated and addressable like top-level facts.
- **Kernel size:** `check.py` + `model.py` ≈ 740 lines with docstrings, plus ≈ 210 for JSON parsing/rendering. Over "a few hundred" because rejection reasons are spelled out per rule; nothing domain-specific is in it.
- **Purity is enforced by a test** that parses kernel imports and allows only the stdlib (and forbids `socket`, `urllib`, `http`, `subprocess`).
