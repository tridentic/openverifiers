# KDScript-Domain — syntax specification (v1 curly-brace)

A declarative, harness-authored grammar language. NOT Turing-complete: no
loops, no free code. Curly-brace blocks, typed fields with `:` annotations —
a Pythonic/C# type-hint hybrid. The compiler turns a document into a v2
`Grammar` (Registry dispatch, provenance tiers, owner/frame reification).

Core model:

    Transformation: Facts -> Facts, provided the input facts satisfy the
    declared inner conditions. The grammar hosts the transformations;
    a proof applies them fact by fact. Fact identity is semantic —
    "Velocity belongs to PointObject, measured in ReferenceFrame" —
    never a variable name.

## Document shape

```
domain <name> {
    unit: <token>, ...                  # built-in unit references
    unit <name> = base(<dim>) | <expr>  # derivations: "kg * m / s^2"

    entity <Name> { }
    entity <Name> extends <Parent> { }
    object <id>: <EntityType>

    fact <Name> {                       # fact struct schema
        owner: <EntityType>             #   belongs to an object of this type
        frame: <EntityType>             #   measured in a frame of this type
        value: float | bool | string
        unit: <token>                   #   quantity structs
        kind: <str>                     #   action structs
    }
    fact <id>: <StructName> {           # frozen-context instance
        owner: <object-id>
        frame: <object-id>
        value: <scalar>
    }

    relation <name> {
        inputs: { <var>: <Struct>, ... }
        equation: <lhs> == <rhs>        # sympy-compatible; any direction
        out: <var> | <var>: <Struct>
        param: [<p>, ...]               # step-bound variables
        guard: [<guard>(...), ...]
    }

    transform <name> {
        builtin: <builtin>              # or: relation: <existing>
        param: [<p>, ...]
        input: [<role>: <Struct>, ...]
        guard: [<guard>(...), ...]
    }

    judge <name> {
        model: <backend>
        input: [<role>: <Struct>, ...]
        schema: <field>: <type>(<opt>|<opt>)
    }

    exclusive: (<a>, <b>, ...)
}
```

Blocks may open inline (`entity PointObject { }`); fields are `key: value`
lines within a block; `#` comments start at end of line.

## Semantics

**Fact structs are the type system.** A struct field:
- `owner: E` — the fact must carry an object of entity type E (engine
  checks `isinstance`; subclasses accepted → polymorphism);
- `frame: E` — the fact must carry a frame of entity type E;
- `unit: t` — typed quantity dimension (any-direction solving);
- `kind: k` — ActionFact kind match.

Typed inputs AUTO-GENERATE the engine-evaluated guards. Relations with a
framed output (`out: vrel: Velocity` where Velocity declares frame) inherit
the common input frame; an owner-typed output inherits the common owner.

**Guards (declarative conditions, engine-evaluated, never agent-claimed):**

| guard | meaning |
|---|---|
| `same_owner(a,b)` | shared owner |
| `different_owner(a,b)` | distinct owners |
| `frame_eq(a,b)` | one shared frame |
| `unit(r, token)` | role carries the declared dimension |
| `kind(r, quantity\|action)` | role is that fact kind |
| `framed(r)` | role carries a frame |
| `owner_of_type(r, E)` | role's owner is entity type E |
| `frame_of_type(r, E)` | role's frame is entity type E |
| `positive(r)` | role's numeric value > 0 |

Free solve-variables are never guarded — the engine computes them.

**Entity round-trip.** `object tiger: PointObject` compiles to a real
PhysicalObject instance; an instance fact `fact v_tiger: Velocity { owner:
tiger, frame: ground, value: 12 }` binds the REAL objects by identity. A
proof step consuming v_tiger carries owner/frame through to its outputs.
`tests/test_kerscript_chase.py` is the round-trip proof.

**Judged steps** stamp results at the `judged` provenance tier with model +
confidence + evidence; deterministic stubs today, Jev behind the same
registry.

## Example

```
domain physics {
    unit: m, kg, s, N, m/s

    entity PointObject { }
    entity ReferenceFrame { }

    fact t_N { unit: N }
    fact t_kg { unit: kg }

    relation dyn.fma {
        inputs: { F: t_N, m: t_kg, a: t_m_s_2 }
        equation: F == m * a
        out: F
    }
}
```