# KDScript-Domain — the complete language reference

This document defines the **domain language**: the file format that teaches
the Verifier one field's permanent knowledge. It is a complete, standalone
reference — read once, in order. After this you can write a domain document
for any field.

The other two languages (context, proof) are separate documents; the domain
only declares what a field IS.

---

## 1. What a domain document is

A domain document is a **static vocabulary**: the things a field talks
about, the units they carry, and the laws that relate them. It is:

- written once, by an engineer;
- **frozen** after review — the proof language can apply its laws but never
  redefine them;
- **data, not code** — no control flow, no functions, no model calls.

Unlike a programming language, a domain document cannot compute anything by
itself. It only declares. A new field (math, physics, law) is a new text
file, never a change to the engine.

The full skeleton of a domain document:

```kerscript
domain <name> {

    namespace <name> {
        entity <Name> [extends <Parent>]
        object <id>: <EntityType>

        type <Name> {
            has:   <EntityType>        # optional
            in:    <EntityType>        # optional
            value: <unit-token>
            kind:  <str>               # for non-quantity facts
        }

        relates(<rel_name>, <arg>, ...)      # declared structure relations

        device <name>(<params>) = <atoms>    # higher-order fact constructors

        law <name>(<param>: <Type>, ...)
            where  <condition>, <condition>
            asserts
                <device-call>

        adjudge <name>(<arg>: <Type>, ...) -> <out>: <Type>

        constant <Name> { value: <scalar>, unit: <unit-token> }
        reference <Type> {
            property <name>: quantity<<unit-token>>
        }
        data <table>: <file.csv>
    }
}
```

Every block below explains one line of this skeleton with a full example.

---

## 2. Namespaces

A namespace is a named block that scopes every declaration inside it. It
exists because real fields are large: physics has mechanics and optics;
they both might define a `Energy` type, and those are DIFFERENT types.

Declarations inside a namespace belong to it. From outside, you refer to
them `namespace.name`. `namespace` is a scoping block, never a dotted
string injected into a name.

```kerscript
domain physics {

    namespace mechanics {
        type Energy { value: J }        # mechanics.Energy
    }

    namespace optics {
        type Energy { value: J }        # optics.Energy — distinct
    }
}
```

Rule: **locals win, qualification resolves ambiguity.** Inside `mechanics`,
a bare `Energy` is `mechanics.Energy`. Cross-namespace references use the
qualified form and are checked at compile time.

---

## 3. Entities — classes (individuals belong to CONTEXT, not here)

An **entity** is a class of individuals. The domain declares the CLASS;
which specific individuals exist belongs to the CONTEXT document (a scene
instantiates its own tiger, ball, or frame). A domain document never names
individuals — no `object tiger: Tiger` in grammar.

```kerscript
namespace mechanics {

    entity PointObject                    # a class of individuals
    entity Vehicle extends PointObject    # every Vehicle IS-A PointObject
    entity Deer    extends PointObject
    entity ReferenceFrame
}
```

Subclassing (`extends`) gives polymorphism: any type that accepts
`PointObject` also accepts `Tiger` and `Deer` — those DECLARE the classes
here, but the tiger itself is born in a context scene. There is no multiple
inheritance and no dynamic class creation — entities are nominal and fixed
at domain time.

The single exception: canonical individuals created by the DATA layer
(constants, reference-table rows, §12) live at domain level because they
are permanent facts of the field, never scene actors.

---

## 4. Types — fact shapes

A **type** is the SHAPE of a fact: what kind of individual it belongs to
(`has`), optionally what frame it is measured in (`in`), and what its value
is. A type is a schema — it is NEVER itself a fact. You cannot have "a
Velocity"; you have *the velocity OF the tiger measured IN the ground,
which is 12 m/s*.

```kerscript
type Velocity {
    has:   PointObject       # a Velocity belongs to a PointObject
    in:    ReferenceFrame    # ... and is measured in a frame
    value: m/s               # the unit its value carries
}

type Claim {
    kind: claim              # non-quantity fact: a proposition, not a number
}
```

Two kinds of facts fall out of this:

- **quantity facts** — the type declares a `value: <unit>`; instances are
  unit-checked numbers.
- **action facts** — the type declares a `kind: <str>`; instances are
  classifications (claims, verdicts, elements), no unit.

The fields `has`, `in`, `value`, `kind` are all optional; an
ownerless/frameless type is legal (mathematical quantities have no owner).

---

## 5. The atom layer — what a fact fundamentally is

A fact is a **predication**: a relator applied to arguments. The core
defines a CLOSED set of relators — the smallest set that can express any
fact. Almost everything you build later (equations, laws) is a composition
of these atoms.

| relator | meaning | example |
|---|---|---|
| `has` | a property of one individual | `has(value, speed, tiger, m/s)` |
| `defines` | definitional identity | `defines(momentum, mass * velocity)` |
| `compare` | order/equality on values | `compare(value(F), value(F2), >=)` |
| `type` | classification | `type(tiger, PointObject)` |
| `relates` | a declared n-ary structure relation | `relates(before, t1, t2)` |
| `implies` | conditional `P and Q => R` | implication between facts |

Notes on the set:

- **There is no bare `contrast`.** Distinctness of individuals is implicit
  in object identity (two objects are distinct by construction); inequality
  of values is `compare(value(a), value(b), !=)`. The `compare` operator
  set is `= < > <= >= !=`.
- **`relates` is the one structural atom** — it stores asserted structure
  between individuals (order, partonomy, graph edges) that comparisons and
  values cannot express. Its vocabulary is FIXED PER NAMESPACE:

  ```kerscript
  namespace law {
      relates(before, t1, t2)      # declares: "before" is a valid relate
      relates(part_of, x, y)
  }
  ```

  Any `relates(other_name, ...)` elsewhere is rejected at parse. Same
  discipline as entity classes: declare it, or it does not exist.

The atom set is **frozen**. A new atom is a core escalation, not a domain
edit.

---

## 6. The raw fact forms

The four direct fact forms you can place in a domain document (or, for the
third, in a context document — it is the same syntax everywhere):

| form | syntax | becomes |
|---|---|---|
| given fact | `fact <id>: <Type> { value: ... }` | a `has` atom on that individual |
| definition | `defines(<name>, <expression>)` | a `defines` atom |
| comparison | `compare(value(a), value(b), <op>)` | a `compare` atom |
| structure | `relates(before, t1, t2)` | a `relates` atom |

Verification of a value happens against atoms: the engine checks a produced
fact by testing the declared atom against the bound values.

---

## 7. Devices — higher-order facts built on atoms

Equations, inequalities, and proportionals are NOT atomic. They are
**devices**: named constructors that build a composition of atoms. The core
ships a few; any domain may declare more over the same atoms.

```kerscript
device eq(a, b)                  = compare(value(a), value(b), =)
device ineq(a, b, <)             = compare(value(a), value(b), <)
device proportional(f, m, k)     = relates(constant_k, k) and
                                   compare(value(f), k*value(m), =)
```

A device is a higher-order logical device: it is not a new atom, it is a
composition of frozen atoms. A domain that needs `eq`, `ineq`,
`proportional`, or anything else simply declares it. Anything a device
composes must be expressible in atoms — otherwise it is not a device, it
is an adjudgment (section 11).

---

## 8. Laws — the powerhouse

A **law** is the unit of derivation. It is a typed, multi-output relation
over device expressions. It has NO single declared output, NO `inputs`
god-object, NO guard list: every parameter is typed, conditions are
declared inline, and EVERY parameter is a potential solution slot.

```kerscript
namespace mechanics {

    law fma(F: Force, m: Mass, k: Ratio)
        where  positive(m)
        asserts
            eq(value(F), k * value(m))

    law v_rel(Vt: Velocity, Vd: Velocity, Vr: Velocity)
        where  different-owner(Vt, Vd)
             , same-frame(Vt, Vd)
        asserts
            eq(value(Vr), diff(value(Vt), value(Vd)))
}
```

What this means:

- `law fma(F: Force, m: Mass, k: Ratio)` declares the signature: three
  parameters, each with a type. `Force`, `Mass`, `Ratio` are types from
  section 4.
- `where ...` declares the CONDITIONS the application must satisfy —
  atomic predicates over the parameters (section 9).
- `asserts ...` declares the DEVICE relationship the law embodies.

Because the law is directionless, the proof can apply it and solve for ANY
slot: bind `F` and `m`, get `k`; bind `k` and `m`, get `F`. One
declaration, many derivations — proportionality needs no special machinery.
The worked trace (section 13) proves this through the engine.

An inequality law is the same construct, emitting a comparison fact rather
than a scalar:

```kerscript
law threshold(x: Length, y: Length)
    asserts
        ineq(value(x), value(y), <)
```

Applying it yields the constraint `x < y`, not a single number.

---

## 9. Conditions (`where`)

The `where` clause declares what must hold for the law to apply. Conditions
are drawn from the CLOSED atom vocabulary — the same predicates the engine
can check deterministically:

| condition | meaning |
|---|---|
| `positive(x)` | x's value must be > 0 |
| `unit(x, <token>)` | x must carry the declared unit dimension |
| `type(x, <EntityType>)` | x's structure must classify as the entity type |
| `different-owner(a, b)` | a and b must belong to DISTINCT individuals |
| `same-owner(a, b)` | a and b must share one individual |
| `same-frame(a, b)` | a and b must be measured in the same frame |
| `exists(x)` | x must be a bound input, never a free solve variable |
| `fixed(a, ...)` | reading condition: these params are invariant for a proportional reading |

Conditions are engine-checked. A law application whose inputs violate a
condition fails deterministically, with the failing condition named.

- `fixed(...)` is a READING condition, not a variable: it marks which
  parameters a proportional reading of the law holds constant. It changes
  what the law ASSERTS, not how it computes.
- There is no free-form condition language, no lambda, no code. The set is
  closed; a domain cannot invent a condition without a core escalation.

---

## 10. `config` — apply-time structural options

Separate from conditions, a law application may pass structural options
that configure HOW a transform operates — a vector axis index, a root
preference. These are never facts and never solved:

```kerscript
momentum(..., with axis=1)
```

`config` answers "how should this transform operate"; `fixed` answers "what
does this law assert is invariant". They are deliberately distinct and
cannot be folded: one controls the engine behavior, the other declares a
reading condition.

---

## 11. Adjudgment — the model-backed seam

An **adjudgment** is a declared step whose result CANNOT be computed
deterministically: a verdict, an agreement, a judgment. It has typed inputs
and a typed output schema.

```kerscript
adjudge agreement(Subj: Claim, Obj: Claim) -> verdict: Vote
```

Crucially, **no model name ever appears in the grammar.** WHICH model
answers an adjudgment is a runtime choice of the user (bound at run time,
per proof). The domain declares the seam and the schema; the engine stamps
the result at the `judged` tier.

---

## 12. The DATA layer — baseline facts, three loci

A domain carries permanent facts separate from its vocabulary: universal
constants and reference tables. These are baseline facts — immutable,
canonical, and never supplied by a problem.

### 12a. Constants (hand-authored baseline)

```kerscript
constant G   { value: 6.674e-11, unit: m^3/(kg s^2) }
constant pi  { value: 3.14159,   unit: dimless }
constant c   { value: 2.998e8,   unit: m/s }
constant h   { value: 6.626e-34, unit: J s }
constant e   { value: 1.602e-19, unit: C }
constant k_Coulomb { value: 8.988e9, unit: N m^2/C^2 }
constant N_A { value: 6.022e23,  unit: 1/mol }
```

Each compiles into a `has` atom about a canonical domain object.

### 12b. Reference tables (generated baseline)

A small hand-authored shape...

```kerscript
reference Material {
    property specific_heat: quantity<J/(kg K)>
    property resistivity:   quantity<Ohm m>
    property refractive_index: quantity<dimless>
}
data material_table: materials.csv
```

...backed by a generated data file (`materials.csv`). The compiler turns
each row into a canonical object plus `has` facts:

```text
row: copper, 385, 1.68e-8, 1.52
  -> object copper: Material
  -> has(specific_heat, copper, 385, J/(kg K))
  -> has(resistivity, copper, 1.68e-8, Ohm m)
```

The reference stays OUT of the law/atom section and OUT of per-scenario
context. Large tables never bloat the domain document.

### 12c. The three loci, one predication

```
has(value, G, 6.674e-11, m^3/(kg s^2))     # constant        : baseline, immutable
has(specific_heat, copper, 385, J/(kg K))  # reference table : baseline, immutable
has(value, v_ball, 12, m/s)                # scenario context: mutable given
```

Same atom, three declaration sites. The merger REJECTS any context fact
whose id collides with a baseline constant/reference id — a problem cannot
omit or zero a universal constant, because that constant is not in the
problem's namespace to supply. This closes the "G=0" leak class
structurally.

---

## 13. Worked proportionality trace (closure-proven)

The constant slot is a first-class law variable. This trace ran through the
actual engine, both facts produced by solving — nothing hand-asserted:

```
law fma(F: Force, m: Mass, k: Ratio)  asserts eq(value(F), k * value(m))

STEP 1: k  = laws.fma(F=f1, m=m1)        # bind k from (F=50 N, m=5 kg)
STEP 2: F2 = laws.fma(k=k, m=m2)         # reuse SAME k, solve F (m=8 kg)

verdict: pass
k  = 10.0          # F/m, unit-checked Ratio
F2 = 80.0 N        # k*m
```

The engine bound `k` → 10 from the known pair, threaded the SAME fact into
the second solve, and derived `F2` → 80 N. No proportionality machinery
exists — the slot is an ordinary variable.

---

## 14. Output propagation (frozen rule)

When a law's application produces a fact typed with a struct carrying
owner/frame:

- **Frame**: collect input frames. 0 → output frameless; exactly 1
  distinct → output keeps it; ≥2 distinct → **reject** (no valid common
  frame).
- **Owner**: 0 → ownerless; exactly 1 → that owner; ≥2 distinct →
  **ownerless is VALID** (a relative quantity has no single owner), never
  an error, rendered distinctly in traces.

Declared conditions are the legal filters; this rule is the engine's
backstop — a step passing its conditions but violating this rule is still
rejected.

---

## 15. Field composition

A domain builds on another by qualified reference. Physics law expressions
may call math devices (algebra, trig) as sub-compositions; the registry is
loaded with both domains and resolves qualification. This is how a HUGE
math domain sits under a huge physics domain: same type system, same
device layer, laws calling laws.

---

## 16. Complete worked domain — everything above at once

A pure-field domain, exercising every section — no scenario actors, per §3:

```kerscript
domain physics {

    namespace mechanics {
        # §3 classes only (individuals live in context scenes)
        entity PointObject
        entity Tiger extends PointObject
        entity Deer  extends PointObject
        entity ReferenceFrame

        # §4 shapes
        type Velocity {
            has:   PointObject
            in:    ReferenceFrame
            value: m/s
        }
        type Mass { value: kg }

        # §5 declared structure
        relates(after, t1, t2)

        # §7 devices
        device eq(a, b)       = compare(value(a), value(b), =)

        # §8 laws
        law v_rel(Vt: Velocity, Vd: Velocity, Vr: Velocity)
            where  different-owner(Vt, Vd)
                 , same-frame(Vt, Vd)
            asserts
                eq(value(Vr), value(Vt) - value(Vd))

        law fma(F: Force, m: Mass, a: Acceleration)
            where  fixed(a)
            asserts
                eq(value(F), value(m) * value(a))

        # §12a constants (canonical individuals: legal at domain level)
        constant G { value: 6.674e-11, unit: m^3/(kg s^2) }
    }

    namespace thermo {
        # §12b reference tables
        reference Material {
            property specific_heat: quantity<J/(kg K)>
        }
        data material_table: materials.csv
    }
}
```

The tiger, the deer, the ground — all born in the CONTEXT document for the
scene that needs them. The domain only supplies the classes, types, laws,
constants, and tables. That is the domain language in one reading.