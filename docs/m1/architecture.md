# OpenVerifiers architecture (Milestone 1)

How the system works from start to finish, in 13 diagrams. Everything here
matches the code on `m1-kernel`. The numbers come from
[`benchmarks/results/latest.md`](../benchmarks/results/latest.md).
Diagrams are Mermaid, so GitHub and most editors render them.

1. [System and trust boundary](#1-system-and-trust-boundary)
2. [`check()` in four stages](#2-check-in-four-stages)
3. [Per-step gates](#3-per-step-gates)
4. [Data model](#4-data-model)
5. [Fact status lifecycle](#5-fact-status-lifecycle)
6. [Trust tiers and grade decision](#6-trust-tiers-and-grade-decision)
7. [Math pack](#7-math-pack)
8. [code_requirements pack](#8-code_requirements-pack)
9. [Repair loop](#9-repair-loop)
10. [Proposers and the repair demo](#10-proposers-and-the-repair-demo)
11. [Mutation benchmark pipeline](#11-mutation-benchmark-pipeline)
12. [Measured catch rates](#12-measured-catch-rates)
13. [Guarantees, assumptions and gaps](#13-guarantees-assumptions-and-gaps)

---

## 1. System and trust boundary

Proposers are untrusted and only emit proofs. The kernel is trusted. It is
stdlib-only, pure and deterministic, and it calls domain logic only through the
hooks a `DomainPack` registers. Packs are trusted the way a proof assistant's
standard library is: they are reviewed code, never proposer input.

```mermaid
flowchart LR
  subgraph U["UNTRUSTED: may be wrong or adversarial"]
    direction TB
    FC["ForwardChainer"]
    BD["BackwardDecomposer"]
    LLM["LLMProposer<br/>complete(prompt) -> str<br/>(ScriptedModel in tests)"]
    HUM["person / case file<br/>candidate_proof"]
  end

  subgraph IN["Inputs (JSON case)"]
    F["initial facts<br/>truth | unverified | target | unknown"]
    R["requirements<br/>selector + predicate + args"]
  end

  subgraph T["TRUSTED BASE"]
    direction TB
    K["kernel.check()<br/>check.py + model.py<br/>stdlib only, no I/O"]
    S["kernel.serialize<br/>strict JSON in/out"]
  end

  subgraph P["DOMAIN PACKS (reviewed code)"]
    M["math<br/>units, sympy, z3, CODATA"]
    C["code_requirements<br/>pytest + hypothesis in subprocess"]
  end

  FC & BD & LLM & HUM -->|Proof| S
  F & R --> S
  S --> K
  K -->|"calls hooks: validate, equal,<br/>precondition, effect, checker, predicate"| M
  K --> C
  K --> V["Verdict<br/>valid, trust_grade, failures,<br/>soft_steps, unverified_facts,<br/>support, trace"]
  V -->|"failure_trail as Feedback"| LLM
  V --> CLI["ov check / trace / solve / bench / demo<br/>exit 0 valid, 1 rejected, 2 malformed"]
```

Hard rule: a pack never needs a kernel change. `git diff 5caedc4 -- openverifiers/kernel`
is empty across both packs.

---

## 2. `check()` in four stages

`check(initial_facts, requirements, proof, pack) -> Verdict`. It does not stop
at the first error. Every step ends up accepted, rejected or skipped, so the
trace is usable as repair feedback.

```mermaid
flowchart TB
  A["check(facts, requirements, proof, pack)"] --> S1

  subgraph S1["Stage 1: structure"]
    direction TB
    s1a["flatten children into one fact index"]
    s1b["per fact: type registered? validate() ok?<br/>unknown has why_unknown? initial not 'derived'?"]
    s1c["duplicate fact ids / step ids"]
    s1d["transformation exists in pack?"]
    s1e["outputs only fill initial target/unknown slots"]
    s1f["every input id = initial fact or some step's output"]
    s1g["build DAG from fact ids, Kahn toposort<br/>cyclic steps + everything downstream"]
    s1a --> s1b --> s1c --> s1d --> s1e --> s1f --> s1g
  end

  S1 --> S2
  subgraph S2["Stage 2: steps in topological order"]
    direction TB
    s2a{"upstream step failed?"}
    s2a -->|yes| s2s["skip: dependency_failed"]
    s2a -->|no| s2r["_run_step: 10 gates, see diagram 3"]
    s2r -->|accepted| s2st["add produced facts to state<br/>status = derived, provenance = step"]
    s2r -->|rejected| s2f["record failures"]
  end

  S2 --> S3
  subgraph S3["Stage 3: requirements on final state"]
    direction TB
    s3a["selector: fact_id, or 'where' over attributes/type/owner/unit"]
    s3b{"matches"}
    s3b -->|0| s3c["requirement_unmatched / requirement_not_reached"]
    s3b -->|">1"| s3d["requirement_ambiguous"]
    s3b -->|1| s3e{"status"}
    s3e -->|unknown| s3u["requirement_unknown"]
    s3e -->|ok| s3p["predicate: exists | equals | pack predicate<br/>raise => fail closed"]
    s3a --> s3b
  end

  S3 --> S4
  subgraph S4["Stage 4: support set and grade"]
    direction TB
    s4a["support = steps the satisfied requirements<br/>transitively depend on"]
    s4b["grade over support only, see diagram 6"]
    s4a --> s4b
  end

  S4 --> V["Verdict + TraceEvent list"]
```

Failure codes (25, in `model.FAILURE_CODES`):

| stage | codes |
|---|---|
| structure | `duplicate_step_id`, `duplicate_fact_id`, `unknown_fact_type`, `invalid_fact`, `unknown_transformation`, `missing_input`, `cycle` |
| steps | `dependency_failed`, `input_role_mismatch`, `output_role_mismatch`, `input_type_mismatch`, `input_not_established`, `input_unknown`, `precondition_failed`, `effect_error`, `output_mismatch`, `checker_rejected`, `checker_error`, `citation_missing` |
| requirements | `requirement_unmatched`, `requirement_ambiguous`, `requirement_unknown`, `requirement_not_reached`, `requirement_failed`, `unknown_predicate` |

---

## 3. Per-step gates

`_run_step` stops at the first failing gate for that step. Every hook
exception is caught and turned into a failure ("fail closed"), and is never
propagated.

```mermaid
flowchart TB
  start(["step s: transformation t, inputs, claimed outputs, params"]) --> g1
  g1{"1. input roles = t.inputs?"} -->|no| f1["input_role_mismatch"]
  g1 --> g2{"2. output roles = t.outputs?"}
  g2 -->|no| f2["output_role_mismatch"]
  g2 --> g3{"3. each input established?"}
  g3 -->|target| f3["input_not_established"]
  g3 -->|unknown| f3b["input_unknown<br/>+ evidence_needed"]
  g3 --> g4{"4. input types match?"}
  g4 -->|no| f4["input_type_mismatch"]
  g4 --> g5{"5. claimed output types match?"}
  g5 -->|no| f5["output_mismatch"]
  g5 --> g6{"6. every precondition returns None?"}
  g6 -->|reason or raise| f6["precondition_failed"]
  g6 --> g7{"7. effect present?"}
  g7 -->|yes| g7a["recompute = effect(inputs, params)<br/>raise / wrong roles: effect_error"]
  g7a --> g7b{"8. claimed == recomputed?<br/>FactType.equal per output"}
  g7b -->|no| f7["output_mismatch<br/>(shows claimed vs recomputed)"]
  g7b -->|yes| use["state gets RECOMPUTED facts"]
  g7 -->|no| useC["state gets claimed facts<br/>only if checker accepts"]
  use --> g8
  useC --> g8
  g8{"9. checker present?<br/>checker(inputs, outputs, params)"} -->|reason| f8["checker_rejected"]
  g8 -->|raise| f8b["checker_error"]
  g8 --> g9{"10. tier == grounded?<br/>each output cites id in pack.sources"}
  g9 -->|missing| f9["citation_missing"]
  g9 --> ok(["ACCEPTED: stamp status=derived,<br/>provenance=(step, transformation, tier, citation)"])
```

Equality is pack-defined. The default is: same type, unit and owner, and values
`isclose(rel=1e-9, abs=1e-12)` for numbers, `==` otherwise. The math pack
overrides it to compare quantities after SI conversion.

---

## 4. Data model

All kernel types are frozen dataclasses in `openverifiers/kernel/model.py`.

```mermaid
classDiagram
  direction LR
  class Fact {
    id: str
    type: str
    value: Any
    unit: str?
    owner: str?
    status: truth|unverified|derived|target|unknown
    attributes: dict
    children: tuple~Fact~
    provenance: Provenance?
    why_unknown: str?
    evidence_needed: tuple~str~
  }
  class Provenance {
    step_id
    transformation
    tier
    citation?
  }
  class Requirement {
    id
    selector: Selector
    predicate = "exists"
    args: dict
  }
  class Selector {
    fact_id?
    where: dict
  }
  class Transformation {
    id
    tier: hard|grounded|soft
    inputs: role->type
    outputs: role->type
    preconditions: tuple~Precondition~
    effect?(inputs, params) -> outputs
    checker?(inputs, outputs, params) -> reason?
    doc
  }
  class Precondition {
    name
    check(inputs, params) -> reason?
  }
  class Step {
    id
    transformation: str
    inputs: role->fact id
    outputs: role->Fact
    params: dict
  }
  class Proof { steps: tuple~Step~ }
  class FactType {
    name
    validate?(fact) -> reason?
    equal?(a, b) -> bool
  }
  class DomainPack {
    name
    fact_types
    transformations
    predicates
    sources
  }
  class Verdict {
    valid: bool
    trust_grade
    failures: tuple~Failure~
    soft_steps
    unverified_facts
    support
    trace: tuple~TraceEvent~
  }
  class Failure {
    code
    message
    step_id?
    requirement_id?
    precondition?
    facts
  }
  Fact --> Provenance
  Fact o-- Fact : children
  Requirement --> Selector
  Transformation o-- Precondition
  Proof o-- Step
  Step ..> Transformation : by id
  Step o-- Fact : claimed outputs
  DomainPack o-- FactType
  DomainPack o-- Transformation
  Verdict o-- Failure
```

`DomainPack` refuses to construct if a predicate shadows a built-in (`exists`,
`equals`) or a transformation names an unregistered fact type.

---

## 5. Fact status lifecycle

```mermaid
stateDiagram-v2
  [*] --> truth : given, trusted
  [*] --> unverified : given, e.g. extracted
  [*] --> target : slot to fill
  [*] --> unknown : needs why_unknown
  target --> derived : accepted step output
  unknown --> derived : accepted step output
  truth --> truth : usable as input
  unverified --> unverified : usable, grade becomes conditional
  derived --> derived : usable as input
  target --> target : as input → input_not_established
  unknown --> unknown : as input → input_unknown (+evidence_needed)
  note right of derived
    Only the kernel assigns derived.
    An initial fact claiming it is invalid_fact.
    Re-defining any established id is duplicate_fact_id.
  end note
```

---

## 6. Trust tiers and grade decision

| tier | what the kernel checks | what the pack checks |
|---|---|---|
| `hard` | recompute equals claim, or checker accepts | the math/test logic |
| `grounded` | the citation id exists in `pack.sources` | that the source content supports the claim |
| `soft` | only that it is a declared soft transformation | judgment; accepted conditionally |

The grade is computed only over the **support set**. A soft step that no
satisfied requirement depends on does not lower the grade. Any failure anywhere
still makes the proof invalid.

```mermaid
flowchart TB
  q0{"any failure?"} -->|no| q1
  q0 -->|yes| qu{"all failures in {input_unknown,<br/>requirement_unknown, dependency_failed,<br/>requirement_not_reached}<br/>and at least one unknown?"}
  qu -->|yes| UND["undetermined<br/>(can't tell yet)"]
  qu -->|no| INV["invalid<br/>(something is wrong)"]
  q1{"support has a soft step?"} -->|yes| CS["conditional_on_soft_steps<br/>lists soft_steps"]
  q1 -->|no| q2{"support rests on unverified<br/>initial facts?"}
  q2 -->|yes| CU["conditional_on_unverified_facts<br/>lists unverified_facts"]
  q2 -->|no| q3{"support has a grounded step?"}
  q3 -->|yes| GR["grounded"]
  q3 -->|no| FH["fully_hard"]
```

---

## 7. Math pack

`openverifiers/domains/math/` provides 30 transformations. Units are strings
parsed into 7-exponent SI dimension vectors.

```mermaid
flowchart LR
  subgraph FT["fact types"]
    Q["quantity<br/>value + unit<br/>equal: convert to SI, isclose"]
    EQ["equation<br/>text, untrusted"]
  end

  subgraph UN["units.py"]
    u1["parse 'kg*m/s^2'<br/>left to right, no parens"]
    u2["dimension → (L,M,T,I,Θ,N,J)"]
    u3["to_si / si_unit / mul"]
    u1 --> u2 --> u3
  end

  subgraph TR["transformations"]
    AR["arith.add / sub<br/>precondition: same_dimension"]
    MD["arith.mul / div<br/>result in SI units<br/>div: nonzero_divisor"]
    SL["algebra.solve_linear<br/>pre: linear_in_one_unknown<br/>safe parse, z3 proves<br/>root exists + unique"]
    CL["constant.lookup (grounded)<br/>cites CODATA: g_n, c, e"]
    FO["7 pack-authored formulas<br/>→ 24 solve_var transformations<br/>pre: dimensions, domain<br/>sympy solve + residual check"]
  end

  subgraph PR["predicates"]
    p1["has_dimension"]
    p2["approx (rel tol)"]
  end

  SAFE["parse_side: char allowlist,<br/>no dunders, no builtins,<br/>every name → plain Symbol"] --> SL
  SAFE --> FO
  UN --> AR & MD & FO
  FO --> AMB{"one admissible root?<br/>(nonnegative vars)"}
  AMB -->|no| EE["effect_error, never a guess"]
```

Proposers cannot submit their own "hard" formula. Formulas exist only as pack
code.

---

## 8. code_requirements pack

```mermaid
flowchart TB
  spec["spec fact<br/>function + R1..Rn text"]
  suite["check_suite fact<br/>tests named test_Rk_*"]
  rep0["report fact (target)"]

  spec --> s1["s1 code.implement (hard)<br/>no effect; static checker:<br/>parses, defines fn, denylist"]
  s1 --> src["source fact (claimed, checker-accepted)"]

  spec & src & suite --> s2["s2 code.run_checks (hard)<br/>precondition suite_covers_spec:<br/>≥1 test per Rk"]
  s2 --> sb

  subgraph sb["effect run_suite: subprocess"]
    direction TB
    b1["temp dir: solution + tests"]
    b2["python -I -m pytest, scrubbed env"]
    b3["30 s timeout, RLIMIT_CPU"]
    b4["hypothesis derandomized, DB off"]
    b5["parse junit XML → results per Rk"]
    b1 --> b2 --> b3 --> b4 --> b5
  end

  sb --> cmp{"claimed report == recomputed?"}
  cmp -->|no| om["output_mismatch<br/>(false 'all passed' caught)"]
  cmp -->|yes| rep["report: derived"]
  rep0 -.filled by.-> rep
  rep --> preds["predicates: all_checks_pass,<br/>requirement_passes(Rk)"]
  sb -->|timeout| to["'timeout' report → mismatch, not exception"]
```

Limit: the pack trusts the compiled checks. If the tests under-specify a
requirement, wrong code passes.

---

## 9. Repair loop

`proposers/repair.py`. The kernel is the only judge in the loop.

```mermaid
flowchart TB
  st(["case: facts + requirements + pack"]) --> pr["proposer.propose(state, reqs, pack, feedback)"]
  pr --> parse{"reply parses as Proof?"}
  parse -->|no| up["Attempt failed:<br/>unparseable_proposal (proposer-side code)"]
  parse -->|yes| k["kernel.check()"]
  k --> v{"verdict.valid?"}
  v -->|yes| done(["RepairResult: accepted,<br/>attempts, final verdict"])
  v -->|no| fb["Feedback = failure_trail:<br/>codes, step ids, claimed vs recomputed,<br/>evidence_needed"]
  up --> fb
  fb --> lim{"attempts < max?"}
  lim -->|yes| pr
  lim -->|no| gave(["RepairResult: rejected"])
  k -.-> log["jsonl_logger: one line per attempt"]
```

---

## 10. Proposers and the repair demo

```mermaid
flowchart LR
  subgraph FWD["ForwardChainer"]
    f1["from established facts"] --> f2["try transformations with effects<br/>priority: fill target → fully-named roles → rest"]
    f2 --> f3["novelty filter, max_steps=60"]
    f3 --> f4["prune to kernel support set"]
  end
  subgraph BWD["BackwardDecomposer"]
    b1["from each requirement's target"] --> b2["pick solve_var producing it"]
    b2 --> b3["recurse on missing inputs"] --> b4["emit steps, prune"]
  end
  subgraph LL["LLMProposer"]
    l1["build_prompt(facts, reqs,<br/>transformations, feedback)"] --> l2["complete(prompt)"] --> l3["parse_reply: JSON,<br/>optionally fenced"]
  end
```

Search proposers bind roles by `attributes.symbol` or id. They solve 4 of 7
math cases (forward) and 3 of 7 (backward).

`ov demo repair` (braking-force case, scripted model):

```mermaid
sequenceDiagram
  participant M as ScriptedModel
  participant L as LLMProposer
  participant K as kernel.check
  L->>M: prompt (no feedback)
  M-->>L: proof with a = +5 m/s^2
  L->>K: attempt 1
  K-->>L: invalid: output_mismatch (claimed +5, recomputed -5), dependents skipped
  L->>M: prompt + structured failures
  M-->>L: proof with a = -5 m/s^2, F = -6000 N
  L->>K: attempt 2
  K-->>L: valid, fully_hard
  Note over L,K: test asserts the 2nd prompt carried the failures
```

---

## 11. Mutation benchmark pipeline

```mermaid
flowchart LR
  cases["benchmarks/cases<br/>math: 7, code: 2<br/>(valid base proofs)"] --> mut["mutations.py<br/>9 operators on JSON case<br/>+ per-domain PERTURB hooks"]
  mut --> mu["mutants (labeled)<br/>math 112, code 28<br/>n/a where operator doesn't apply"]
  cases --> base["base cases<br/>(false-rejection check)"]
  mu & base --> setups
  subgraph setups["3 setups"]
    nv["no_verification<br/>accept everything"]
    mj["mock_llm_judge<br/>deterministic, reads<br/>final claims only"]
    kr["kernel<br/>check()"]
  end
  setups --> score["score: caught?<br/>right reason? (EXPECTED_CODES)"]
  score --> out["results/latest.md + latest.json<br/>per mutation × domain"]
```

Operators: `unit_mismatch`, `sign_error`, `dropped_step`,
`missing_precondition` (remove a consumed premise), `wrong_effect`,
`unreachable_target`, `duplicated_fact_id`, `circular_dependency`, plus
`misread_given` (consistent misreading of a given number).

---

## 12. Measured catch rates

Math domain, catch rate % per mutation (mock judge vs kernel). Order on the
x-axis: unit, sign, dropped, missing_pre, wrong_effect, unreachable, dup_id,
cycle, misread.

```mermaid
xychart-beta
  title "Math: catch rate by mutation (bar = kernel, line = mock LLM judge)"
  x-axis [unit, sign, dropped, missing_pre, wrong_eff, unreach, dup_id, cycle, misread]
  y-axis "% caught" 0 --> 100
  bar [100, 100, 100, 100, 100, 100, 100, 100, 93.8]
  line [0, 41.7, 63.6, 0, 41.7, 100, 58.3, 0, 37.5]
```

| domain | mutants | no verification | mock LLM judge | kernel | right reason | false rejections |
|---|---|---|---|---|---|---|
| math | 112 | 0.0% | 34.8% | 99.1% | 99.1% | 0 / 7 |
| code_requirements | 28 | 0.0% | 50.0% | 100.0% | 100.0% | 0 / 2 |

The one miss is `math_drop_speed~misread_given~0`. The mass is misread as
2 → 4 kg and everything after it is recomputed consistently. Impact speed
doesn't depend on mass, so the requirement still holds. The kernel checks
proofs against their requirements, not against intent.

These operators each break a rule the kernel was built to check, so this is a
regression suite, not evidence about real proposer error distributions.

---

## 13. Guarantees, assumptions and gaps

```mermaid
flowchart LR
  subgraph G["GUARANTEED by the kernel"]
    g1["no step result taken on trust:<br/>recomputed or checker-accepted"]
    g2["DAG well-formed: no cycles,<br/>no missing inputs, no redefinition"]
    g3["hook exceptions fail closed"]
    g4["unknown never silently passes"]
    g5["grade reflects weakest tier<br/>in the support set"]
    g6["deterministic, pure, stdlib-only<br/>(import test enforces it)"]
  end
  subgraph A["ASSUMED (outside the kernel)"]
    a1["pack hooks are correct"]
    a2["requirements capture intent"]
    a3["truth facts are true"]
    a4["code checks cover the spec"]
    a5["sympy is right<br/>(residual check not independent)"]
  end
  subgraph X["KNOWN GAPS"]
    x1["misread givens the requirements<br/>don't pin down"]
    x2["sandbox is isolation, not security"]
    x3["no real LLM run yet;<br/>judge column is a mock"]
    x4["small samples: 7 math, 2 code"]
    x5["search proposers: formula-shaped only"]
    x6["CI not yet run; 3.11 untested locally"]
  end
  subgraph D["EXTERNAL DEPENDENCIES"]
    d1["sympy: formula solving"]
    d2["z3-solver: linear uniqueness"]
    d3["pytest + hypothesis: code checks"]
    d4["CODATA values: grounded sources"]
  end
  D --> A
  A --> G
```
