# OpenVerifiers — Pythonic Polymorphic Grammar DX

**Status: spec (accepted direction). Engine migration staged: the class-based DX
replaces the string-kind/`make_rule` authoring surface; the shipped physics slice
and its 20/20 benchmark stay green until the new surface is proven equivalent.**

This is the authoring contract a domain developer writes against. It is not a
replacement of the core ontology (Fact / Transformation / Unknown) — it is the
*DX* over it: everything the author touches is Python classes with attributes,
nesting, and polymorphism, never string tokens and dict configs.

---

## 1. The core idea

A grammar is a set of **Python classes**, not string tables. The author models the
domain the way they'd model any strongly-typed domain in Python:

```python
# the domain === the code === the grammar. No separate spec layer.
```

Three responsibilities a developer defines *in code*:

1. **Entities / facts as classes** — with typed attributes and nesting.
2. **Logic as transformation classes** — each declaring typed inputs and a typed
   output, gated by a typed precondition.
3. **A proof footprint** — every fired transformation leaves a trace node linking
   output fact → input facts → the rule → its source premises, walkable backwards.

Everything else (search, DAG, dedup, verdict, trace render) is the engine's job and
the author never touches it.

---

## 2. Facts as classes

A fact class declares its `kind`, its typed attributes, and — crucially — **nesting**.
A fact may contain sub-facts. This is how a `Body` composes a `Rod` composes a
`Joint`; how an `Order` composes items, carriers, and a deadline.

```python
class Physical(ctx):
    """Base: any class with ctx-scoped instantiation is a Fact in the grammar."""

@dataclass(frozen=True)
class Quantity(Physical):
    kind: str          # "velocity"
    value: float
    unit: str          # "m/s"
    dimension: Dim     # D_VELOCITY

@dataclass(frozen=True)
class Body(Physical):
    name: str
    mass: Quantity     # sub-fact (typed nesting)
    parts: tuple[Body, ...]  # recursive composition — a cube IS a body with faces

@dataclass(frozen=True)
class Joint(Physical):
    at: tuple[float, float, float]
    members: tuple[Body, ...]
```

Polymorphism — the same abstract rule operates over any subtype:

```python
class Moveable(Protocol):
    mass: Quantity

@dataclass(frozen=True)
class Cube(Body): ...      # is a Body, is Moveable
@dataclass(frozen=True)
class Rod(Body): ...       # is a Body, is Moveable

# a rule typed against the protocol accepts Cube, Rod, or any Body subtype —
# this is where the engine's single energy rule K = .5 m v^2 already works
# for mass-bearing objects regardless of concrete shape.
```

### Why nesting matters for the proof footprint

A nested fact's sub-facts are material to what can be proven about it. Deriving a
joint reaction requires the members facts; a sub-fact change invalidates parent
derivations. Nesting IS the recursive type model the site already advertises
("a car decomposes into chassis, engine, and so on"); here it becomes a first-class
authoring primitive with typed slots, not an afterthought.

---

## 3. Transformations as classes

A rule is a class with declared input types and an output type — not a function
named by a string.

```python
@dataclass(frozen=True)
class Transformation(Generic[In, Out]):
    symbol: str                    # stable identity, e.g. "kinematics.v_u_at"
    name: str                      # human label
    inputs: tuple[Type[In], ...]   # typed role signatures (the SoT of arity/types)
    output: Type[Out]              # typed output

    def precondition(self, facts: tuple[In, ...]) -> str | None:
        """Typed gate. Return None = may fire; reason string = rejection (traced)."""
        ...

    def apply(self, facts: tuple[In, ...]) -> tuple[Out, str]:
        """Produce the typed output fact + a trace note."""

    @property
    def solver_hook(self) -> str: ...   # "sympy.algebra" | "z3.sat" | "statistical"

class v_u_at(Transformation[Quantity, Quantity]):
    # author writes precondition + apply; engine supplies list/apply directions.
```

Per-role typed preconditions (owner, unit, dimension, type) become **Python
validation on the input signatures**, not dict strings:

```python
class s_from_u_a_t(Transformation[ tuple[Quantity, Quantity, Quantity], Quantity ]):
    def precondition(self, facts):
        u, a, t = facts
        if u.unit != "m/s":  return f"expected m/s, got {u.unit}"
        if a.dimension is not D_ACCEL: return f"expected acceleration dim, got {a.dimension}"
        if t.unit != "s":     return f"expected s, got {t.unit}"
        return None
```

Polymorphism is the engine's gate: a rule typed at `Moveable` accepts any subtype.
The engine's dimension/type/owner checks become the author's native Python type
system instead of rhythmless string equality.

---

## 4. The proof footprint

Every derivable result carries a **footprint back to its premises** — the walkable
origin chain. A derived `Quantity` for a `Joint` doesn't just carry a number; it
carries references to the radius, the torque, the attached `Rod` facts, and the
`Transformation` name that produced it, recursively.

This is what makes the footprint audit-safe:
- `derived.origin` = the transformation node
- `derived.premises` = the input facts (each with their own footprint)
- walking `derived.origin → premises → …` bottoms out in `truth` axioms or
  source-typed `given` facts.

It is also what powers **persistence** (next section).

---

## 5. Derived-fact persistence + invalidation (the OpenWiki move)

**The idea.** Proved facts/premises persist across runs, each **linked back to the
original content they came from** (code, a physics setup, a source document). If that
content changes, every derivation rooted in it is **revalidated** — the persisted
verdicts that depended on the changed source are flagged stale and re-derived.

**Why this compounds.** No longer do we re-prove everything from scratch every run.
We cache the proof graph. A physics sandbox that "just implements this system" is
**logic-ready from day 1**: attach a rod to a cube corner, the joint reaction facts
persist; rotate the rod, only the chain depending on the rotation re-validates, and
every downstream conclusion recomputes — this is incremental proof.

**The persistence model** (mirrors OpenWiki mechanics):

| concept | meaning |
|---|---|
| `source` | the original content/knowledge unit a fact was built from (the code line, the sandbox component, the source paragraph). Versioned. |
| `proved` | a derived fact + its full footprint, persisted with the `source` it roots to. |
| `source_version` | a monotonic version/hash of the content. |
| `derives_from(source_id, version)` | provenance edge: this proved-fact depends on that source at that version. |
| revalidation | when a `source_version` bumps, every persisted fact whose transitive footprint touches it is **marked stale**; re-deriving only the affected subgraph re-persists it. |

```python
with ovf.VerificationContext() as ctx:
    rod = SandboxBody(klass="rod", length=Quantity(2.0,"m"), mass=Quantity(3.0,"kg"))
    cube = SandboxBody(klass="cube", edge=Quantity(0.5,"m"), corners=8)
    # attach rod to cube corner faces[0]
    rod_joint = ctx.attach(rod, to=cube.corners[0])      # a Transformation firing
    reaction = joint_reaction(rod_joint).evaluate()       # derived + persisted

# state is saved. Later:
ctx.source_bumped(rod)      # rod length edited
ctx.revalidate()            # reaction facts whose footprint includes rod are stale -> re-derived
```

### Interplay with the DAG prohibition on cycles

Persistence does not cycle the proof graph. A persisted derived fact is still a node
with strictly-decreasing premise dependencies; revalidation walks the same DAG, only
pruned to the stale subgraph. The audit rubric (walk to `truth`/root with strictly
decreasing dependency) is unchanged — persistence is a caching layer over an acyclic
proof store, which is exactly why it cannot smuggle circular reasoning.

---

## 6. The U-Net framing (messy input → formal setting → prove → conclude)

The user's framing is upstream of the DX and worth fixing in words: an agent receives
**messy, mixed textual + visual** problem content; the pipeline is

```
messy text + image/problem  ──►  schema-forced extraction  ──►  formal logical setting
                                                                     ▲
    (U-Net "boil down")                                              │ typed facts/rules
                                                                     ▼
                             conclusion  ◄──  derive/verify over the setting
```

- **Boil down**: extract structured typed facts + target from messy input (the
  encoder of the U-Net). The classes in §2 ARE the hidden/latent space — a fixed,
  typed representation of the messy world.
- **Prove**: run the engine over the formal setting (the DAG of class-typed
  transformations).
- **Conclude**: the derived verdict + footprint (the decoder — but here decoding is
  lossless: it renders the proof, never invents steps).

This is not a metaphor — it is the contract. A domain is "logic-ready since day 1"
exactly when its extraction maps messy input onto the class-typed fact space and its
proof machinery runs the same class-typed transformations.

---

## 7. Migration staging (accepted: specify now, migrate later)

| step | content | risk |
|---|---|---|
| 1 (this pass) | DX spec above is the contract; no engine change | none — 20/20 stays green |
| 2 | build one domain (logistics or rod/cube sandbox) in class-DX as a parallel grammar, prove equivalence on shared fixtures | moderate — must match `make_rule` results |
| 3 | swap `Builder.make_rule` path for class-typed `Transformation`; keep `sympy.algebra` hook | controlled — benchmark gates |
| 4 | add `source` + footprint persistence + revalidation | additive — new store, old results legible |

The engine's `Transformation` already carries `roles` (owner/type/unit/dimension)
and `solver_hook`; step 2–3 is teaching the author surface to be typed classes while
the engine internals hold. The alive physics slice is the safety net.

---

## 8. What this adds to the status DB

Each case study's `verifiable_because` now names the **typed class surface** it needs
and whether it is **persistence-relevant** (source-linked revalidation). The
`framework_lesson` per domain already points at engine needs; the DX spec is the
shared authoring contract those lessons accumulate into.