# KDScript-Domain — syntax specification (v1)

A declarative, harness-authored grammar language. NOT Turing-complete: no
loops, no free code. A document declares units, types, objects, facts,
relations, transformations, and judged steps; the compiler turns it into a
v2 `Grammar` (Registry dispatch, provenance tiers, owner/frame reification).

The core model, stated plainly:

    Transformation: Facts -> Facts, provided the input facts satisfy the
    declared inner conditions. The grammar is the host that holds the
    transformations; a proof applies them fact by fact.

## File structure

```
domain <name>                      # required first statement
doc <free text>

namespace <name>                   # indentation-scoped nesting
    ...declarations...             # names resolve relative to the scope

type <name> = <base>               # base: fact | quantity | action | entity
type <name> extends <base> [unit(<token>)]     # quantity subtype
type <name> extends <base> [kind(<str>)]       # action subtype
type <name> extends <base> [framed]            # readonly: requires a frame

unit <token>, <token>              # reference built-in tokens
unit <name> = <expr>               # derive: "kg * m / s^2", "base(length)"

object <id>: <entity-type> [frame(<obj>)]      # object instances

fact <id>: quantity(<value>, <unit>) [owner(<obj>)] [frame(<obj>)]
fact <id>: action(<kind>, <value>)  [of=<x>]

relation <name>: <expr> unit(<v>=<unit-or-type>,...) out(<v>) [param(<p>,...)]
transform <name>: builtin(<builtin>) [param(<p>,...)] [input(<r>:<type>,...)]
                  [guard(<g>,...)] [doc(<text>)]
transform <name>: relation(<rel>) [guard(<g>,...)]
judge <name>: model(<m>) input(<r>:<type>,...) schema(<f>=<type>[|<opt>],...)

exclusive(<a>, <b>, ...)
```

## Semantics

**Names.** A declaration inside `namespace foo` (nested: `foo.bar`) gets that
prefix; a name written with explicit dots is kept as written. No full
qualification required anywhere.

**Types.** `type X extends quantity unit(m)` declares a unit-dimension typed
role; a bound input fact must be a Quantity with that dimension. `extends`
with base `entity` builds a nominal object class (polymorphism: a role typed
by a base accepts subtypes). `framed` types must carry a reference frame on
the fact; a relation with a framed output inherits the common input frame.

**Relations.** One symbolic relation per declaration, solvable in any
direction by the engine (bind all-but-one -> numeric solve, positive root
preferred; all bound -> consistency check; two-or-more free -> symbolic
ExpressionFact). `=` separates the two sides; `**` is power; `sqrt`,
`pi` available. `param(...)` declares step params that may bind variables
(e.g. `rate_pct`).

**Transforms.** Two kinds: `builtin(...)` resolves a core logical primitive
(modus ponens, induction machinery, law checklist), `relation(...)` wraps a
declared relation (e.g. to attach guards). Typed inputs auto-generate
guards; explicit `guard(...)` entries add declarative conditions.

**Guards (declarative conditions; engine-evaluated, never agent-claimed):**

| guard | meaning |
|---|---|
| `same_owner(a,b)` | both facts share one owner |
| `frame_eq(a,b)` | both facts carry one frame |
| `kind(r, quantity\|action)` | role is that fact kind |
| `unit(r, token)` | role's unit dimension matches |
| `framed(r)` | role carries a reference frame |
| `positive(r)` | role's numeric value > 0 |

**Judged steps.** `judge` names a model backend, typed inputs, and an output
schema. The engine stamps the result at the `judged` provenance tier with
model, confidence, and evidence. Backends (deterministic stubs today, Jev
later) plug into one registry; the document never changes.

## Example

```
domain physics
doc High-school physics relations, one per transformation.

type PointObject = entity
object car: PointObject

type force   extends quantity unit(N)
type mass    extends quantity unit(kg)
type accel   extends quantity unit(m/s^2)

relation dyn.fma: F = m * a  unit(F=force, m=mass, a=accel)  out(F)
```