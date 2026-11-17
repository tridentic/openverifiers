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

## Math pack

- **Units are strings parsed into 7-exponent SI dimension vectors** (no parentheses, left-to-right). This is enough for kinematics, dynamics, energy and circuits, and stays JSON-friendly.
- **Formulas are pack-authored; each one registers a `solve_<var>` transformation per variable.** A proposer must never be able to submit its own "hard" formula. This also gives fixed role signatures, which the search proposers rely on.
- **Formula effects solve with sympy, and a separate residual check substitutes back.** The check is cheap but not independent of sympy; this is noted in STATUS.
- **`algebra.solve_linear` uses z3** to prove existence and uniqueness of the root, and compares it with the claim.
- **Equation text is untrusted**, so it is parsed with a character allowlist, no dunders, no builtins, and every identifier forced to a plain Symbol (`E` and `I` are not constants).
- **mul/div results are expressed in SI units**, which avoids composing unit strings. Quantity equality converts units, so a claim in km/h still matches.
- **Ambiguous roots are an `effect_error`, not a guess.** `nonnegative` variables pick the non-negative root only when exactly one remains.

## Benchmark

- **Mutation operators work on the JSON-level case**, with per-domain value-perturbation hooks. Kinds that don't apply to a domain show as n/a, not as 0.
- **"Missing precondition" means a premise the proof consumes is removed** from the given facts (the proof rests on an unestablished premise). Dropping a role binding would only test signature checking.
- **"Unreachable target" points a requirement at a fact nothing produces.**
- **"Right reason" is reported separately from "caught"**, using the failure codes that are expected for each label.
- **`misread_given` was added beyond the eight requested kinds:** a consistent misreading of one given number. It is the cheapest way to show the kernel's real boundary: it checks proofs against requirements, not intent.
- **The LLM judge is a deterministic mock that reads only final claims**, and is labeled as such everywhere. Faking "LLM-like" randomness would add noise without adding information.
- **`benchmarks` is included in the setuptools package list** so `ov bench run` works from an editable install. Distribution packaging is a non-goal.

## Proposers

- **`Proposer` is a Protocol** (`propose(state, requirements, pack, feedback)`), so any object with that method works.
- **The search proposers bind roles to facts by name** (`attributes.symbol` or id), falling back to any fact of the right type. They use only transformations with effects, and prune to the kernel's support set.
- **Forward chaining prioritizes target-filling, then fully-named bindings, then everything else, with a novelty filter and a step cap.** Unrestricted arithmetic made it explode in the first version.
- **The LLM adapter takes `complete(prompt) -> str`** (no SDK dependency); replies must be JSON proofs, optionally fenced.
- **An unparseable reply counts as a failed attempt** with failure code `unparseable_proposal` (a proposer-side code, not a kernel one) and is fed back like any other failure.
- **The repair demo uses a scripted model and asserts that the second prompt carried the structured failures.** It demonstrates the loop, not model quality.

## code_requirements pack

- **Requirements become tests named `test_Rk_*`; a requirement passes only if all its tests pass.** The id is read from the test name, so mapping needs no extra metadata.
- **`code.implement` has no effect (code can't be recomputed) and a static checker** (parses, defines the function, small denylist). `code.run_checks` has an effect that reruns the suite, so a false "all passed" claim is an `output_mismatch`.
- **`run_checks` takes the spec as an input**, so its precondition can require a test for every stated requirement.
- **Hypothesis is derandomized and the hypothesis database is disabled** in the subprocess, so the effect is deterministic for deterministic tests.
- **A timeout produces a `timeout` report rather than an exception.** The claimed report then mismatches, and the trace says why.
- **Case JSON embeds source files from `benchmarks/sources/`;** `python -m benchmarks.build_code_cases` rebuilds them.
