# OpenVerifiers v1: M-CAP progress report

**To:** CTO · **Date:** 2026-11-22 · **Branch:** `v1` at `b5220db`

Every number comes from a command run today. The detailed record is in the
commit messages of `6ec80fe` and `b5220db`, and in KNOWN_LIMITATIONS.md.

## Bottom line

**Done:**
- **The two "keep" items from §0.**
  - The quick q11 fixes: WHAT IF by label lookup, plus a parse cache.
  - CI is stable again; the `bench` job now has wide margin.
- **The start of §1, the library restructuring,** for `math.core`,
  `math.calculus` (new), `math.geometry` and `physics.mechanics`.
- **Pythagoras and SUVAT are PROVEN theorems,** as you required before the
  first exam problem.
- **`ov audit`** exists.

**Not started: the exam problem sets (§3).** Nothing is drawn, formalized or
benchmarked yet. **I need your decision on sources** before I start (§6).
The HSC-tier report you asked for therefore does not exist yet. This is a
progress report.

0 false PROVEN still holds on everything that runs.

## 1. §0: CI and the q11 limit (`6ec80fe`)

- **WHAT IF RETRACT no longer re-runs the program.**
  - A fact that some WHAT IF retracts is lowered as a hidden assumption,
    active by default.
  - Retracting it is a context change, answered from the labels the kernel
    already computed.
  - Hidden names never appear in an answer's assumptions.
- **Parsed packages are cached** by file and text.
- **Effect on q11 `ov check`:** p50 **0.102 s → 0.046 s**, p95 0.110 s →
  0.056 s (locally). On GitHub's runner, about 3x slower, that is roughly
  0.15 s against the 300 ms limit. The `bench` job has passed since.
- **Side fix:** an UNKNOWN answer whose missing piece is an assumption now
  names the statement (`reviewed(v2)`), not an internal `assume` atom.
  - `agentic/deploy_checklist` now passes.
  - The ratchet's list of known mismatches shrank.
  - Bench: **34/36, 0 false PROVEN.**

## 2. §1: few axioms, many theorems (`b5220db`)

**Language changes.** Every one is core, not tied to a domain.

| change | what it is | domains it serves today |
|---|---|---|
| axiom kinds | package rules: `axiom` (foundation), `law` (empirical), `definition`. Class members: `invariant` (definition), `law`, `theorem`, `lemma` | physics (Newton as `law`), math (definitions), chemistry and logic rules (kinds to be assigned) |
| exact polynomial calculus | `integral(e, t)` (from 0 to t) and `deriv(e, t)`. The trusted evaluator decides them exactly: it samples `e` at t = 0..degree, recovers the coefficients, then integrates or differentiates | math.calculus, kinematics, (later) areas and extrema in exam math |
| quantities in classes | quantity-typed properties and unknowns; formulas and pattern values dimension-checked (E301); answers print with units (`?s = 21 m`) | physics; chemistry (moles, molarity); agentic (money) |
| lemmas | a theorem z3 cannot settle from the invariants is retried with the theorems already PROVEN in its class and ancestors. UNPROVEN theorems are never used | every package with layered theorems |

**Library status.** Every theorem in all four packages is PROVEN. Each
package has 10+ tests, all passing.

| package | axioms (foundation / law / definition) | theorems | PROVEN | axiom ratio |
|---|---|---|---|---|
| math.core | 9 (1 / 0 / 8) | 9 | 9 | 0.50 |
| math.calculus | 4 (2 / 0 / 2) | 11 | 11 | **0.27** |
| math.geometry | 17 (4 / 0 / 13) | 8 | 8 | 0.68 |
| physics.mechanics | 18 (2 / 6 / 10) | 10 | 10 | 0.64 |

**What is proven:**
- **math.core:** the quadratic formula (as the completed square), the
  discriminant conditions, Vieta (sum and product), AM–GM for two numbers,
  and the sum of squares.
- **math.calculus:** the power, constant, linearity and product rules, both
  directions of the fundamental theorem for cubics, the vertex of a quadratic,
  and the area under a line.
- **math.geometry:** Pythagoras, the parallelogram, rectangle, rhombus and
  square properties, and the section formula.
- **physics.mechanics:**
  - velocity and displacement are *defined* as integrals of acceleration;
  - all five SUVAT equations, work–energy, mechanical energy conservation
    under gravity, momentum conservation and impulse are *proven*;
  - Newton's second and third laws and weight are the only `law`s.

**Theorem DAGs** (`ov audit --dag`):
- **Pythagoras** rests on the coordinate foundations alone: the distance
  formula, angles by dot product, and arithmetic. It needs no class
  invariant.
- **SUVAT `v² = u² + 2as`** rests on the two integral definitions,
  `velocity` and `displacement`.
- **Energy conservation** rests on work–energy, which rests on Newton's
  second law and SUVAT, which rest on the integral definitions; plus the
  `weight` law.
- **Momentum conservation** rests on the two velocity definitions and
  Newton's second law (both bodies) and third law.

**Trust.** Every PROVEN theorem's `trust_base` is `{z3_unsat}`, plus the
reductions used (geometry). With `--strict`, all of them become UNKNOWN, as
designed. Polynomial-identity theorems could be checked by trusted normal
form instead of z3; that would make them `{kernel}`. It is not built yet.

**The axiom ratio is not where you want it.** The target is ≤ 0.25 for
physics and math. Only math.calculus is close (0.27).
- Physics and geometry are high because each class carries its own
  definitions (positivity, elapsed time, the velocity definitions repeated
  for two bodies).
- I have not added theorems to move the number. It should fall as exam
  problems need real lemmas, and as classes can reuse other classes instead
  of restating their definitions.

**A definition bug found on the way, fixed before commit.**
- Elapsed time could be negative, so the speed of a dropped ball came back
  as both +10 and −10 m/s.
- The class now defines `t >= 0`.
- No wrong answer reached a benchmark, but this is the kind of modelling
  error the faithfulness reviewer in §3 must catch.

## 3. Health at head

| check | result |
|---|---|
| tests | **530 passed**, 0 failed (+4 timing tests in the `bench` job) |
| bench (36 cases) | 34/36, **0 false PROVEN**, 0 false REFUTED, 0 seed variance |
| coverage, trusted and kernel code | 99% (`raw/formula.py` 98%; gate 95%) |
| trusted code size | **1,470 / 1,500** (was 1,413; +57 for exact calculus) |
| gold gate | passes over every commit since step 2 |
| CI | **all 6 jobs green** at `6ec80fe` and at `b5220db` (tests on 4 platforms, `bench` timing, gold gate) |

**Trusted code is nearly full.** The next trusted addition (for example,
normal-form checking of polynomial identities) needs the split you approved
in v1.1: `raw/formula.py` as its own audited unit, capped at 400 lines.

## 4. Honest weaknesses so far

These are expected JEE and A-level failure classes. Each one is
`language_gap` in the §4 taxonomy.

- **No sin/cos of a general angle.** Angles are exact only at 0, 30, 45, 60,
  90, 120, 135, 150 and 180 degrees. Inclined planes, projectiles and
  resolving forces at arbitrary angles cannot be written. **This is the
  largest physics gap.**
- **No sums over a symbolic number of terms.** The sum of an arithmetic
  progression with n terms needs a sum operator or induction.
- **Distances are not arithmetic.** `dist + dist` is refused (E405); use
  `dist2`.
- **Calculus covers polynomials in one variable.** There are no
  exponentials, logarithms or numeric ODEs. So radioactive decay and RC
  circuits are gaps.
- **No class composition.** A class cannot contain instances of another
  class. Multi-body problems restate definitions, which also inflates the
  axiom ratio.
- **FIND does not name missing facts** (`physics/push_block` q2). PROVE does.

## 5. Not started (in your order)

- Restructuring `chem.organic` and the remaining packages to §1. This
  includes assigning axiom kinds to the organic rules.
- `physics.electric`, thermal physics, optics and modern physics.
- `chem.core`: stoichiometry, balancing as integer linear constraints, pH.
- The agentic package: tool-call gate, plan synthesis.
- The problem sets, the faithfulness lint and reviewer, and the capability
  report.

## 6. Decision needed: where the problems and gold come from

The directive requires real past papers, with gold taken from the **official
answer key**.

- **JEE Advanced:** official papers and answer keys are published by the
  organising IIT. Usable.
- **Cambridge 9702 / 9701 / 9709:** official mark schemes exist, but
  Cambridge distributes them through its school portal. Public copies are
  third-party mirrors.
- **Bangladesh HSC (board questions):** I do not know of any publicly
  available official answer key. If none exists, HSC gold cannot meet the
  "official key" rule.

**Options:**
1. **You (or the founder) provide** the papers and keys in a folder. I draw
   the problem list mechanically from them, commit it, then commit gold
   before formalizing.
2. **I fetch them from official sources.** Each download needs your
   explicit approval.
3. **For HSC,** decide what counts as gold if there is no official key, for
   example solutions worked by two people independently, marked as such in
   the report.

Until this is settled, the problem sets (and so the HSC-tier report) are
blocked. Library work can continue in the meantime: the remaining physics
and chemistry packages.
