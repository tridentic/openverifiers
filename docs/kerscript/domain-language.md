# KDScript-Domain — Language Specification v2 (syntax proposal)

Status: **proposal — awaiting approval.** One document, three parts. Every
construct is shown working in a bite-sized example; Part 3 composes every
construct from Parts 1–2 into one runnable domain. No grammar export is
regenerated until this spec is approved.

Semantic core (unchanged, non-negotiable):

    Transformation: Facts -> Facts, provided the input facts satisfy the
    declared inner conditions. The grammar hosts the transformations; a
    proof applies them fact by fact. The engine computes, the agent names.

Keyword discipline (the fix):

| keyword | means |
|---|---|
| `entity` | a typed OBJECT with identity (PointObject, ReferenceFrame) |
| `type`   | a fact SHAPE / schema — typed fields, never an instance |
| `fact`   | a typed INSTANCE / assertion — a specific entity with specific field values |
| `relation` | a RULE — typed inputs, an equation or guard, an output |
| `transform` | an applied step reusing a relation or a builtin, optionally with guards/params |
| `judge`  | a model-backed step with typed output schema |

---

## PART 1 — Type system

### 1.1 Entities: typed objects with identity

An `entity` is a class of objects. Objects (`object`) are the individuals:
real identities a fact can belong to.

```
entity PointObject { }
entity ReferenceFrame { }

object tiger: PointObject
object ground: ReferenceFrame
```

### 1.2 Entity subtyping (is-a)

`extends` declares inheritance. A role typed by the PARENT accepts any
subtype instance (polymorphism).

```
entity PointObject { }
entity Deer extends PointObject { }
entity Tiger extends PointObject { }

object deer: Deer              # a Deer IS a PointObject
object tiger: Tiger            # a Tiger IS a PointObject
```

### 1.3 quantity<Unit> — the generic numeric type

A quantity is ONE generic type, parameterized by its unit. No per-unit
wrapper types, ever. The unit expression lives inside `<>` and may be a
token, a derived name, or a full unit expression.

```
relation dyn.fma {
    inputs: { F: quantity<Newton>, m: quantity<kg>, a: quantity<m/s^2> }
    equation: F == m * a
    out: F
}
```

No `t_Newton`, `t_A`, `t_kg` aliases exist in the language. A unit is not
a type; a quantity is a type-on-a-unit.

Domain vocabulary may still be declared with names, when a relation set
uses the same unit repeatedly — this is naming a UNIT, not declaring a
type:

```
unit Newton = kg * m / s^2          # derived-unit vocabulary

relation dyn.weight {
    inputs: { w: quantity<Newton>, m: quantity<kg>, g: quantity<m/s^2> }
    equation: w == m * g
    out: w
}
```

### 1.4 Struct types: the fact SHAPE

A `type` groups entity-ref fields + a value into one reusable fact shape.
The `value` field is typed with `quantity<Unit>` or a scalar tag.

```
type Velocity {
    owner: PointObject
    frame: ReferenceFrame
    value: quantity<m/s>
}

type Money {
    owner: PointObject
    value: quantity<USD>
}
```

Typed fields ARE conditions: the engine enforces that an instance of
`Velocity` carries a real `PointObject` owner and a `ReferenceFrame` frame,
by identity and by type.

---

## PART 2 — Fact vs Relation

### 2.1 fact = a typed INSTANCE / assertion

A `fact` is one specific claim about one specific entity, with specific
field values. It always names a `type` and concrete object ids. It is
NEVER a type, NEVER a unit alias.

```
object tiger: Tiger
object ground: ReferenceFrame

fact v_tiger: Velocity {
    owner: tiger
    frame: ground
    value: 12
}
```

Reads as: "the Velocity of the tiger, measured in the ground frame, is
12 m/s". The identity is the OBJECT — not a variable name, not a string.

### 2.2 relation = a RULE

A relation has typed inputs, an equation (or guards), and an output. Inputs
come in two shapes — side by side:

**Shape A — scalar quantity inputs only:**

```
relation dyn.fma {
    inputs: { F: quantity<Newton>, m: quantity<kg>, a: quantity<m/s^2> }
    equation: F == m * a
    out: F
}
```

**Shape B — entity-carrying inputs (facts whose fields carry owner/frame
types):**

```
relation chase.relative_speed {
    inputs: { a: Velocity, b: Velocity }        # both carry typed owner+frame
    equation: vrel == a - b
    out: vrel: Velocity                          # framed output
    guard: [different_owner(a, b), frame_eq(a, b)]
}
```

Here `Velocity` is a struct type: the inputs bring `owner` and `frame`
with them, and the engine's type guards (owner_of_type, frame_of_type,
unit) fire automatically. The guards are the extra relational conditions:
distinct owners, one shared frame.

The output `vrel: Velocity` means: the produced fact is a Velocity too —
inheriting the shared frame, with no common owner when owners differ.

### 2.3 What a relation never does

A relation never fabricates facts, never trusts a value the caller
supplies for its output, and never skips its guards. The agent names the
transformation and the inputs; the engine computes the output and decides
legality.

---

## PART 3 — One complete worked example

Every construct from Parts 1–2 in one small domain: entity, subtype,
objects, struct type, fact instances referencing those objects, two
relations consuming facts (entity-carrying and scalar), guards, typed
output — three relations total.

```
domain chase {
    unit: m, s, m/s, m/s^2

    # -- 1: entities + identity + subtyping ----------------------------------
    entity PointObject { }
    entity ReferenceFrame { }
    entity Deer extends PointObject { }
    entity Tiger extends PointObject { }

    object tiger: Tiger
    object deer: Deer
    object ground: ReferenceFrame
    object ground2: ReferenceFrame

    # -- 2: fact shape ---------------------------------------------------------
    type Velocity {
        owner: PointObject              # any PointObject (Deer, Tiger, ...)
        frame: ReferenceFrame
        value: quantity<m/s>
    }

    # -- 3: fact instances (assertions about specific entities) -----------------
    fact v_tiger: Velocity { owner: tiger, frame: ground, value: 12 }
    fact v_deer: Velocity  { owner: deer,  frame: ground, value: 7 }

    # -- 4: relations (rules) ----------------------------------------------------
    # entity-carrying inputs: two Velocities, distinct owners, one frame
    relation chase.relative_speed {
        inputs: { a: Velocity, b: Velocity }
        equation: vrel == a - b
        out: vrel: Velocity
        guard: [different_owner(a, b), frame_eq(a, b)]
    }

    # scalar quantity inputs: gap closes at the relative speed over time
    relation chase.gap_closing {
        inputs: { start: quantity<m>, speed: quantity<m/s>, t: quantity<s> }
        equation: gap == start - speed * t
        out: gap: quantity<m>
    }

    # scalar with a simple guard
    relation chase.miss_step {
        inputs: { gap: quantity<m>, step: quantity<m> }
        equation: ok == gap - step
        out: ok: quantity<m>
        guard: [positive(gap)]
    }
}
```

### Composing it — the proof program

The proof names transformations and inputs; the engine computes:

```
proof closure:
    vrel = chase.relative_speed(a=v_tiger, b=v_deer)   # 5 m/s, frame=ground
    gap  = chase.gap_closing(start=start, speed=vrel, t=t)
    ok   = chase.miss_step(gap=gap, step=step)
```

What the engine guarantees, per step:

1. `vrel`: both inputs are Velocities (typed owner/frame enforced), owners
   DIFFER (deer vs tiger — Deer/Tiger are distinct PointObjects), frames
   AGREE (both ground). Output is a Velocity; its frame is ground (the
   shared input frame); no owner (two distinct owners).
2. `gap`: scalar relation, unit-checked — `start` in m, `speed` in m/s,
   `t` in s ⇒ `gap` in m.
3. `ok`: guard `positive(gap)` is evaluated by the engine; a non-positive
   gap refuses the step with the guard named.

A second frame (`ground2`) exists only to prove the frame guard: using a
velocity measured in `ground2` with one in `ground` fails `frame_eq` and
the step is rejected.

---

## What this changes vs the current implementation

1. `quantity<Unit>` generics replace every `fact t_X { unit: X }` wrapper
   — unit vocabulary stays, wrapper types go.
2. The keyword `fact` is reserved for instances; the previous
   `fact Velocity { ... }` schema form becomes `type Velocity { ... }`.
3. Entity-typed inputs flow through struct types; `owner`/`frame` fields
   become automatic owner_of_type/frame_of_type/unit guards.
4. Everything else (relations, transforms, judges, guards, proof traces)
   is unchanged semantics.

After approval: parser + compiler implement quantities-as-generics and
the `type` keyword; physics.opk is regenerated from this shape; the
dataset gate re-runs.