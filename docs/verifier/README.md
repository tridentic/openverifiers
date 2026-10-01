# KDScript Verifier — Language Family

KDScript is three languages, one per pipeline task. Together: a Verification
Engine combining deterministic proof with model-powered judgment.

```text
domain   -> static vocabulary: namespaces, types, laws, conditions
context  -> ONE scenario: objects, given facts, freeze, target
proof    -> agent-authored: apply laws, loose jumps, adjudgments
```

The invariant: **the agent names, the engine computes, the model grades.**
An agent never submits a value, never declares a fact verified, never names
a model. Every produced fact carries a provenance tier and a confidence;
the target's answer is the aggregate along its derivation chain.

## The three tasks

| artifact | task | who writes | who runs |
|---|---|---|---|
| domain | teach the system a field | engineer (once per field) | compiler, static |
| context | instantiate one problem | assistant + agent | compiler, static |
| proof | solve / attempt | agent | engine + model |

## What a fact is

A fact is a **predication**: a relator applied to arguments over
individuals. `speed(tiger) = 12 m/s in ground`. Equations, inequalities,
proportionals are NOT atomic facts — they are **devices** the domain or the
engine builds on top of the closed predication set. The core freezes the
predications; domains build any higher-order logical device on them.

## Provenance tiers

| tier | meaning | set by |
|---|---|---|
| `verified` | derived by a law; engine checked | engine |
| `extracted` | given in context | context author |
| `assumption-dependent` | holds inside an `assume` scope | engine |
| `judged` | adjudged step, typed schema | adjudgment backend |
| `loose` | agent jump; graded per run | model, at runtime |

Confidence: `verified`/`extracted` = `1.0`; `assumption-dependent` = product
of dependencies; `judged`/`loose` = model score `[0, 1]`. A single graded
step at `p` caps every dependent target at `p`.

## Documents

- `01-domain.md` — domain language: namespaces, types, predications, law
  powerhouses, conditions, adjudgment
- `02-context.md` — context: objects, givens, freeze, target query
- `03-proof-run.md` — proof + run: apply-law selection, loose seam,
  counter-argument protocol, confidence, verdicts