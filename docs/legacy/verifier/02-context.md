# KDScript-Context — one problem, frozen

The context document turns a plain-English problem into typed state:
which objects exist, which facts are given, what is being asked. It is
data — the agent never reasons here, it instantiates.

```kerscript
context chase-problem {
    domain: physics.mechanics        # qualified namespace reference

    object tiger: Tiger
    object deer: Deer
    object ground: ReferenceFrame

    fact v_tiger: Velocity {
        has:   tiger
        in:    ground
        value: 12           # m/s, by the type's declared unit
    }
    fact v_deer: Velocity {
        has:   deer
        in:    ground
        value: 7
    }

    target vrel: Velocity { expected: 5 }
}
```

A context fact may NEVER collide with a domain baseline id (constant or
reference-table object). The merger rejects the collision: a problem cannot
omit or zero a universal constant, because it is not in the problem's
namespace to supply.

## Freeze boundary

On `context` close, givens freeze. After the freeze:

- no new raw facts may enter — only engine-derived or model-graded facts;
- the target query is locked;
- everything the proof produces is a traced derived step.

The scenario is fixed BEFORE the proof runs, so the agent cannot quietly
rewrite the problem while solving it.

## Objects and identity

`object` lines bind entity ids; facts reference them. The compiler keeps
them as real objects (identity, not strings) throughout — the round-trip
proof (`test_kerscript_chase.py`) pins this.

## Target query

`target` declares what the proof must produce: a fact id, a type, expected
value. The run compares the produced fact's value against expected and
carries the confidence of its derivation chain.