# KDScript-Proof — syntax specification (v1)

The agent-facing trace language. It names registered transformations (from
KDScript-Domain grammars), supplies inputs and params, and opens/closes
assumption scopes. NOT Turing-complete: the agent declares intent, the
engine computes and checks.

A proof compiles to v2 `TraceStep` records and runs through the closed
whitelist (`Registry`): unknown transformation names fail closed; the agent
never submits computed values or condition results.

## Syntax

```
proof <name>:                    # optional block header
    z = math.mul(a, b)           # transform step
    q = logic.modus_ponens(implication=imp, antecedent=p)
    fv = business.compound(principal=p) with rate_pct=5, years=2
    ...
    assume H: claim text         # open assumption scope
        step = math.proof_step(predecessor=base) with k=0, expr="2n-1"
    end                          # discharge: H => last product
    end contradiction            # reductio: negate the conflicting claim

    # comments
```

## Step forms

| form | meaning |
|---|---|
| `out = ns.transform(in1, in2)` | apply registered transformation; engine computes output |
| `out = ns.transform(role=fact_id)` | named-role inputs |
| `... with k=v, k2=v2` | step params (scalars: int, float, true/false, `"quoted"`) |
| `assume H: text` | open scope under claim text |
| `end` | conditional discharge -> `ImplicationFact` |
| `end contradiction` | conflict with trusted state -> negation |

References resolve against the frozen background facts and facts this proof
has produced; assumption scopes are nested regions whose products discharge
on close. A fact produced inside a scope never leaks out unqualified.

## Example

```
proof velocity:
    v = kin.suvat_v_u_at(u=u, a=a, t=t)
    s = kin.suvat_s_ut_athalf(u=u, a=a, t=t)
```