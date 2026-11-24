# OpenVerifiers v1 Bedrock: final exit report

**To:** the founder and the CTO · **Date:** 2026-11-24 · **Branch:** `v1` at this
report's commit · MASTERPLAN MP-1.3. Packet 4 stages MP-1.4: D-033, D-034, D-031b.

**Verdict: every v1 exit criterion is met except criterion 6.** Criterion 6
needs 20 CI runs in a row; there are 6 under D-034's counting. Nothing else
remains open, so v1 exits when the streak reaches 20 and you sign packet 4
(MP-1.4 records D-031b, under which criterion 1 is evaluated).

v1 has **one official-key exam tier**: JEE (Advanced) 2025, 30 problems, gold
from the official answer key. No JEE Main source exists
(`private/sources/jee_main/` is absent), so D-031b applies: JEE Main and HSC
are v1.1 tiers.

## 1. Exit criteria (MP §7 v1, as amended by D-030 and D-031b)

| # | criterion | status | evidence |
|---|---|---|---|
| 1 | 0 false PROVEN over every gold-first case: JEE Advanced 30 + agentic 20 + breadth 35 + adversarial 50 (D-031b) | **met** | §2: false PROVEN 0 in every suite (agentic has 22 cases, breadth 35, adversarial 50) and 0 wrong JEE answers |
| 2 | A capability report with the domain × tier matrix and the failure taxonomy | **met** (one tier) | §3: the JEE matrix by subject and outcome, and the taxonomy of all 17 problems not solved |
| 3 | 0 unsound mutants accepted, object path included | **met** | §2: rule path 5,320 / 5,321 killed, the survivor weakened but sound; object path 159 false-claim mutants, all rejected |
| 4 | ≥ 60% of library theorems at `{kernel}` | **met** | 40 / 52 (77%) |
| 5 | Total TCB ≤ 2,300 lines (D-030) | **met** | 2,144 / 2,300 |
| 6 | CI green 20 runs in a row (D-034); `reproduce.sh` regenerates every table | **partial** | `reproduce.sh`: done (it produced every table below). CI: 6 / 20, run IDs in §2 |

## 2. Numbers (MP §8)

All numbers below come from `reproduce.sh` at commit `ed96f9c`, with these
exceptions:
- **Mutants and the `{kernel}` share** were measured at `03681e7`. That commit
  changes only the draft `physics.rotation`, and no benchmark, exam or test
  outcome; the run checked this.
- **The CI streak** comes from `scripts/ci_streak.py`.

**Trusted code (the total is the headline, D-030):**

| unit | lines | cap |
|---|---|---|
| main (raw/, checker/, state/ hash and load) | 1,100 | 1,150 |
| `raw/formula.py` | 449 | 450 |
| unit A (surd, interval, numeric, certificate, qpi) | 595 | 700 |
| **total** | **2,144** | **2,300** |

**Unsound mutants accepted, by path:**

| path | mutants | result |
|---|---|---|
| rule path (`test_checker.py`) | 5,321 non-equivalent | 5,320 killed; 1 weakened but sound; **0 unsound accepted** |
| object path (`test_object_mutants.py`) | 369 | **159 false-claim mutants, all rejected**; 0 unsound accepted |

**Benchmark suites (default and `--strict`):**

| suite | cases | pass (default) | pass (`--strict`) | false PROVEN | false REFUTED | p50 s | p95 s |
|---|---|---|---|---|---|---|---|
| adversarial | 50 | 50 | 50 | 0 | 0 | 0.0008 | 0.0027 |
| agentic | 22 | 22 | 22 | 0 | 0 | 0.0016 | 0.0027 |
| chemistry | 7 | 7 | 7 | 0 | 0 | 0.0387 | 0.0662 |
| geometry | 6 | 6 | 3 | 0 | 0 | 0.0220 | 0.1450 |
| logic | 7 | 7 | 7 | 0 | 0 | 0.0012 | 0.0019 |
| mathematics | 7 | 6 | 5 | 0 | 0 | 0.0020 | 0.0161 |
| physics | 8 | 7 | 7 | 0 | 0 | 0.0037 | 0.0061 |
| **all** | **107** | **105** | **101** | **0** | **0** | **0.0015** | **0.0391** |

- **Breadth** is chemistry, geometry, logic, mathematics and physics: 35 cases.
- **The two default failures** are the long-known mismatches: `mathematics/linear_system`
  is UNKNOWN where the gold is PROVEN; `physics/push_block` gives a different
  reason for its UNKNOWN. Neither is a wrong answer.
- **Under `--strict`**, answers that rest on a z3 unsat become UNKNOWN by design.

**JEE (Advanced) 2025, 30 problems, official keys:**

| mode | solved | unknown | error | wrong | not formalized | provisional | stated assumptions |
|---|---|---|---|---|---|---|---|
| default (drafts loaded) | **13** | 1 | 0 | **0** | 16 | 1 (phys p2q3) | phys p2q3 (N043) |
| `--strict` | **9** | 4 | 1 | **0** | 16 | 0 | none |

- **Uniqueness answers at `{kernel}`:** 5 / 5.
- **Under `--strict`:**
  - **error 1:** phys p2q3, whose `physics.rotation` is a draft;
  - **unknown 4:** answers whose completeness rests on z3.

**Differential testing (5,000 cases, seed 0):**

| class | agree | refused | disagree |
|---|---|---|---|
| solver side (expander vs evaluator) | 4,781 | 219 | **0** |
| exp derivatives | 973 | 27 | **0** |
| surd normal form (D-030) | 1,000 | 0 | **0** |
| positive sums (D-030) | 129 accepted, 871 refused as required | — | **0** |
| ln and 1/u derivatives (D-030) | 997 | 3 | **0** |
| sin and cos, normal form and derivatives (D-033) | 944 | 56 | **0** |

**Other numbers:**

| number | value |
|---|---|
| tests | 652 passed (v1 suite with coverage: 342 passed) |
| trusted-code coverage | 98% |
| faithfulness lint | 0 errors, 4 warnings |
| gold and meaning gates, whole history | ok |
| latency | bench p50 0.0015 s, p95 0.0391 s |

**The CI streak (D-034):** it counts push runs on distinct commits plus the
nightly run, each judged by its first attempt; re-runs don't count. **6**
green in a row:

| run ID | commit | result |
|---|---|---|
| 45239411156 | `23ba5d2` | success |
| 45235861822 | `b989370` | success |
| 45234263963 | `bd2ed44` | success |
| 45232992091 | `7e45263` (the founder's signed packet-3 commit) | success |
| 45229348380 | `b2da61f` | success |
| 45226924917 | `2e97802` | success |
| 45217847806 | `dc04eea` | **broke it**: the first attempt was cancelled (a macOS job got no runner in 15 minutes) |

Pending at writing: `ed96f9c`, `03681e7`. The nightly run counts only once its
schedule fires (packet 4, Part D1).

## 3. Capability report: the JEE tier

**Matrix (default, drafts loaded):**

| subject | solved | unknown | not formalized | of which out of scope |
|---|---|---|---|---|
| chemistry | 3 | 0 | 7 | 6 |
| mathematics | 6 | 0 | 4 | 1 |
| physics | 4 | 1 | 5 | 0 |
| **all** | **13** | **1** | **16** | **7** |

**Failure taxonomy (the 17 not solved):**

| category | count | problems and what they need |
|---|---|---|
| out of scope (directive) | 7 | organic structures and descriptive chemistry; the v2 items |
| language | 4 | math p1q1 (a quantifier over the reals); math p1q13 (a limit); math p2q6 (integrals of square roots); phys p1q5 (exp of ln in the normal form, plus an induction library) |
| library | 4 | phys p1q7 (waves); phys p2q6 (geometric optics); phys p1q16 (atomic and nuclear facts); chem p1q1 (inorganic decomposition) |
| not attempted | 1 | phys p1q1 (rolling and small-oscillation energy) |
| engine | 1 | phys p1q10: real algebraic numbers (deferred to v2 by D-030) |

## 4. What C7 delivered

| work order item (packet 3 reply) | status | commits |
|---|---|---|
| 1. Exit report §3 with the full table; a CI check for unfilled placeholders | done | `b989370` |
| 2. D-033 sin/cos, then N043 | done. N043 proved at `{kernel}`, reviewed twice; the first form was circular and was withdrawn | `23ba5d2`, `03681e7` |
| 3. JEE Main if its source exists | no source: D-031b applies | — |
| 4. Python SDK (docs, API, examples, tests) | done: `openverifiers.sdk`, `docs/SDK.md` | `ed96f9c` |
| 5. The CI streak under D-034 | 6 / 20, building | `b989370` (script, nightly) |
| 6. This report and packet 4 | done | this commit |

**Also fixed in C7:**
- **The trusted record checker** crashed on a certificate term too deep to
  read. It now rejects such a record (`bd2ed44`).
- **The pseudo-division finder** stalled for more than 30 minutes on one exam
  problem. It now has deterministic budgets (`2e97802`).

## 5. Deviations and shortcuts

1. **D-033 grew `raw/formula.py` by 29 lines**, which D-033 did not name (packet
   4, Part D3). Unit A grew 22, within the "~40".
2. **macOS 3.11 moved from push runs to the nightly run** because GitHub's queue
   cancelled it 3 times (packet 4, Part D2).
3. **The first N043 proof used a law that restated the result.** The reviewer
   caught it, and it was withdrawn before any approval.
4. **One red CI run in C7** (`788e599`, an over-long line). The check now runs on
   the linter's exit status before every push.

## 6. Decisions needed

All decisions are in `reports/APPROVAL_PACKET_2026-11-24_packet4.md`:

| part | decision | how it's settled |
|---|---|---|
| A | MP-1.4: D-033, D-034, D-031b | staged; your signed command |
| B | `physics.rotation` with N043 | staged; your signed command |
| C | M078 re-proposed (Quadrilateral excludes three collinear vertices) | staged; your signed command |
| D | the nightly schedule; macOS 3.11; the formula-unit lines; p2q3's assumption | written reply |
