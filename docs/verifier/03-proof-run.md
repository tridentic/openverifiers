# KDScript-Proof — the only agent-run artifact

The proof moves facts -> facts by APPLYING laws. The agent names the law
and binds slot facts; the engine computes the selected output; models grade
what the engine cannot decide. The agent can NOT submit values, cannot
invent conditions, cannot change the frozen context, and cannot skip a
law's declared conditions.

```kerscript
proof <name>:
    vrel: Velocity = laws.v_rel(vt=v_tiger, vd=v_deer)   # solve vrel
    gap:  Length   = laws.gap_closing(start=g0, speed=vrel, t=t)
    assume H: claim text
        x = laws.mul(a, b)
    end                          # H => x
    end contradiction            # H => not(claim)
```

## Apply-law: one law, many derivations

Laws are powerhouses — multi-parameter, no single declared output. An
application binds SOME slots as inputs and NAMES the slot it wants derived.
The engine solves for it. Nothing else is stated.

```kerscript
    # the same law, three directions, zero re-declaration:
    p:   Momentum = laws.momentum(m=m_ball, v=v_ball)
    v:   Velocity = laws.momentum(p=p_rock, m=m_rock)
    m:   Mass     = laws.momentum(p=p_rock, v=v_ball)
```

An inequality law emits a COMPARISON fact (a constraint), not a scalar:

```kerscript
    bound: Compare = laws.threshold(x=x_known, y=y_known)   # e.g. x < y
```

## Step vocabulary (closed)

| step | what it does | tier |
|---|---|---|
| `out: Type = law(slot=..., ...)` | applies a law; engine solves | verified |
| `assume H: claim` / `end` / `end contradiction` | scoped boxes | assumption-dependent |
| `out = adjudge(...)` | declared adjudgment step | judged |
| `out: Type = loose(...) with support: ...` | agent jump, model-reviewed | loose |

Everything else is rejected by the parser. No free-form code, no arbitrary
function call.

## Loose transformations — the model-powered seam

Sometimes no declared law covers the jump, but the step is still sound —
a structural claim, a pattern, a judgment. The agent writes a Loose
Transformation: name the inputs, name the output SHAPE, attach their OWN
supporting reasoning, and declare candidate conditions for verification.

```kerscript
    e_kin: Energy = loose.kinetic_from_falling(m=m, g=g, h=h) with support: \
        "object at height h in uniform gravity: KE gained = m*g*h; potential \
         asserted as candidate energy, to be graded below"
```

The support block is agent text — NOT trusted. The engine wraps it into a
structured grading request to a model backend (e.g. Jev):

1. Package: inputs (typed facts), claimed output, support text, declared
   output schema, the same closed conditions the law would face.
2. Ask the model to CONSTRUCT A COUNTER-ARGUMENT — an attempted
   counterexample, missing condition, misapplied premise.
3. Score: verdict + confidence + reasoning.
4. The output lands tier `loose`, confidence = model score, with the
   counter-argument recorded as evidence.

A successful counter-argument FAILS the step like any condition violation;
downstream targets depending on it cannot pass unqualified.

## Adjudged steps — model chosen at RUN, never in grammar

`out = adjudge.agreement(subject=s1, object=s2)` yields a typed verdict
stamped `judged`, schema-checked against the domain's `adjudge` declaration.
The grammar declares the seam; the USER binds a backend when running:

```text
run proof.agreement --adjudge agreement=jev-3
```

The core cannot tell deterministic stub from LLM backend — it only checks
the schema and stamps the tier.

## Worked proportionality trace (closure-proven)

The constant slot is a first-class law variable; bind it from a known pair,
reuse it, solve forward. Both facts flow through the engine:

```
STEP 1: k  = laws.fma(F=f1, m=m1)        # bind k from (F=50 N, m=5 kg)
STEP 2: F2 = laws.fma(k=k, m=m2)         # reuse SAME k, solve F (m=8 kg)
verdict: pass
k  = 10.0      # F/m, unit-checked
F2 = 80.0 N    # k*m
```

No special proportionality machinery — just equation solving over a
declared constant slot.

## Confidence propagation — uncertainty carried downstream

Every fact carries `(tier, confidence)`:

| tier | confidence |
|---|---|
| verified | 1.0 |
| extracted | 1.0 (presumed true by the problem) |
| assumption-dependent | inherits from scoped consistency; 1.0 while scoped |
| judged | backend score |
| loose | model grading score, per run |

For a target derived through steps, confidence is the multiplicative
combination:

```
final = product(step_confidence)
tier  = lowest tier in the dependency path   # verified > judged > loose
```

A single loose/judged step at p makes every dependent target at most p —
uncertainty is carried downstream, never discarded, never hidden inside a
"pass".

## Verdicts

- `pass` — all steps executed, all conditions met, target matches expected, all verified.
- `pass-graded` — all steps executed, but >=1 loose/judged step; target confidence < 1.0. Passes WITH A SCORE, not with certainty.
- `fail` — a step failed (condition, residual, counter-argument, schema, missing input); trace shows the failing step + reason.
- `invalid` — proof text malformed; no execution.

## Domain layering at proof time

The registry composes many domains. Physics laws call math laws; adjudged
steps call outside the numeric world; all in one trace, all typed, all
traced:

```kerscript
proof hybrid:
    x:   Number  = laws.solve_linear(a=a0, b=b0, c=c0)
    v:   Velocity = laws.v_motion(u=u, a=accel, t=x)
    ok:  Vote    = adjudge.agreement(claim=claim_text, evidence=v)
```