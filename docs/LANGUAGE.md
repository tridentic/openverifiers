# The OV language

OV is how knowledge is written down for OpenVerifiers. A file holds packages
(types, predicates, axioms) and scenarios (entities, facts, assumptions,
queries). The front end checks names, types and units, then lowers everything
to RawOV, the small kernel language in [SEMANTICS.md](SEMANTICS.md). Nothing
in OV is evaluated directly: the kernel evaluates the RawOV program and the
checker verifies the trace.

Run a file:

```bash
python -m openverifiers.runner examples/chem/q11.ov --verbose
```

The runner prints each query's verdict and, with `--verbose`, the proof steps
with their source lines. It also checks every `expect` and exits with status 1
if one fails. `ov FILE.ov` is the same as `ov run FILE.ov`; `ov COMMAND --help` prints
each command's usage, and `openverifiers.sdk` is the library side (docs/SDK.md).

## A first scenario

```ov
package physics.mechanics @0.1
import math.core

type Body { mass: Mass, accel: Accel }
predicate net_force(b: Body, F: Force) world open

axiom newton2(b: Body, F: Force):
  net_force(b, F) -> F = b.mass * b.accel

test newton2_mass {
  scenario t uses physics.mechanics {
    entity block: Body
    fact net_force(block, 10 N)
    fact block.accel = 2 m/s^2
  }
  query FIND ?m WHERE t.block.mass = ?m
  expect PROVEN 5 kg
}
```

- `newton2` is an equation, so it is solved for whichever field is missing:
  here the mass (10 N / 2 m/s² = 5 kg, exactly).
- `F` is checked to be a Force, and `b.mass * b.accel` a Mass × Accel. The two
  dimensions agree, so the axiom is accepted. `kg + m` anywhere is error E301.
- The answer is PROVEN with no assumptions. Its proof is two facts plus one
  application of `newton2`.

## Lexical rules

- **Comments** start with `#` and run to the end of the line.
- **Newlines carry no meaning.** Every statement starts with a keyword, so a
  statement can span lines.
- **Names** are letters, digits and `_`. They may also contain inner hyphens
  (`pent-1-ene`), and may start with digits when a hyphen follows
  (`2-chloropentane`, `1,1-dimethylcyclopropane`).
  - A hyphen joins a part that has a letter in it, or digits followed by
    another hyphen. So `a-b` is one name (write `a - b` to subtract), while
    `i-1` is `i - 1`, as in `v[i-1]`. Error E201 points out a joined name.
- **Quantities** are a number, optionally followed on the same line by a unit:
  `10 N`, `2 m/s^2`, `0.5 kg`, `3 km/h`.
  - Numbers are exact rationals. Decimals are read exactly: `0.1` is 1/10.
  - The unit must be a known unit name (see the units table below). After a
    number, `2 m` is two metres; write `2 * m` to multiply by a variable `m`.
- **Strings** are written `"..."`.
- **Query variables** are written `?x`.

## Grammar (EBNF)

This is the grammar in `src/openverifiers/lang/grammar.lark`. It is LALR(1).
`{x}` means zero or more, `[x]` optional, `"..."` a keyword.

There are five shift/reduce conflicts, all inside class bodies, and each is
resolved as *shift*:

- Four come from conditions written one after another with no separator (as
  in the brief's `Square`). A condition extends as far as it can: after a
  name, `(` starts a call, `{` a pattern, `[` an index, and `-` continues a
  subtraction. Start each condition on a new line with a name, a number or
  `all`.
- The fifth is `->` inside a quantifier: an implication belongs to the
  innermost quantifier over a collection.

`tests/v1/test_objects.py` checks that these five are the only conflicts.

```ebnf
file        = { item } ;
item        = package | import | type | predicate | function | entity | axiom
            | transformation | controller | generator_decl | scenario | test
            | target | query | expect | fact_type ;

package     = "package" dotted [ "@" version ] ;
import      = "import" dotted | "import" "state" STRING "as" NAME ;
type        = "type" NAME [ "extends" NAME ] [ "{" [ field { "," field } ] "}" ] ;
field       = NAME ":" NAME ;
predicate   = "predicate" NAME "(" [ params ] ")" [ output ] [ "world" ( "open" | "closed" ) ] ;
output      = "->" NAME                              (* one value: functional *)
            | "->" "{" NAME { "," NAME } "}" ;       (* a set of values / unordered outputs *)
function    = "function" NAME "(" [ params ] ")" "->" NAME [ "unordered" ] ;
entity      = "entity" names ":" NAME [ "=" expr ] ;
axiom       = "axiom" NAME [ "(" [ params ] ")" ] ":" conj [ "->" conj ] ;
transformation = "transformation" NAME "(" [ params ] ")" "requires" conj "ensures" conj ;
controller  = "controller" NAME "(" [ params ] ")" "{" { ctrl } "}" ;
ctrl        = "pipe" NAME { "->" NAME } | "branch" NAME "|" NAME { "|" NAME } | "guard" conj ;
generator_decl = "generator" NAME "(" [ params ] ")" "yields" NAME "from" expr ;
generator_use  = "generator" names "from" expr ;
scenario    = "scenario" NAME [ "uses" dotted { "," dotted } ] [ "extends" NAME ]
              "{" { stmt } "}" ;
stmt        = entity | fact | assume | generator_use | query | expect | tolerance ;
fact        = "fact" fact_lit { meta } ;
assume      = "assume" NAME ":" fact_lit { meta } ;
meta        = "confidence" NUMBER | "source" STRING ;
tolerance   = "tolerance" NUMBER ;
test        = "test" NAME "{" { scenario | stmt } "}" ;
target      = "target" NAME "{" { "must" conj | "prefer" conj } "}" ;

(* object layer (brief §3.7) *)
fact_type   = "fact" "type" NAME [ "extends" NAME { "," NAME } ] "{" { member } "}" ;
member      = "property" NAME ":" tyexpr
            | "invariant" NAME ":" fbody
            | "theorem" NAME ":" fbody
            | "derived" NAME ":" tyexpr "=" expr ;
tyexpr      = NAME [ "<" tyexpr { "," tyexpr } ">" ] ;      (* Set<Point>, Real *)
fbody       = fseq [ "->" fbody ] ;                      (* P -> Q: implication *)
fseq        = fsimple { fsimple } | { fsimple } fquant ;  (* conditions are conjoined *)
fquant      = ( "exists" | "none" | "all" ) NAME "in" expr ":" fbody ;   (* runs to the end *)
fsimple     = fchain | "all" NAME ":" fchain | "not" fchain ;
fchain      = expr { CMPOP expr } ;                         (* a = b > 0 *)

params      = group { "," group } ;
group       = names ":" NAME [ "=" expr ] ;          (* a, b: Group *)
names       = NAME { "," NAME } ;
dotted      = NAME { "." NAME } ;

query       = "query" okql ;
okql        = "PROVE" lit
            | "FIND" qvar { "," qvar } [ "WHERE" conj ] [ "LIMIT" NUMBER ]
            | "PROVE" "UNIQUE" qvar { "," qvar } [ "WHERE" conj ]
            | "COUNT" qvar { "," qvar } [ "WHERE" conj ]
            | "CHECK" expr "IS" NAME
            | "COUNTEREXAMPLE" dotted
            | "WHAT" "IF" change { "AND" change } "THEN" okql ;
qvar        = QVAR [ ":" NAME ] ;                     (* ?p: Point *)
change      = "RETRACT" fact_lit | "ASSUME" NAME ;
expect      = "expect" VERDICT [ expr { "," expr } ] [ "assuming" "{" [ names ] "}" ] ;
VERDICT     = "PROVEN" | "REFUTED" | "UNKNOWN" | "INCONSISTENT" ;

conj        = lit { "," lit } ;
fact_lit    = lit | expr "->" expr ;                  (* f(x) -> y,  f(x) -> {y, z} *)
lit         = [ "not" ] cmp ;
cmp         = expr [ ( "=" | "!=" | "<" | "<=" | ">" | ">=" ) expr ] | expr "in" expr ;

expr        = sum ;
sum         = product { ( "+" | "-" ) product } ;
product     = unary { ( "*" | "/" ) unary } ;
unary       = "-" unary | power ;
power       = postfix [ "^" unary ] ;
postfix     = atom { "." NAME | "[" expr "]" } | NAME "(" [ expr { "," expr } ] ")"
            | NAME "{" [ NAME "=" expr { "," NAME "=" expr } ] "}" ;   (* pattern T{...} *)
atom        = NAME | QVAR | QUANTITY | STRING | "unknown" | "(" expr ")"
            | "(" expr "," expr { "," expr } ")"                    (* tuple *)
            | "{" [ expr { "," expr } ] "}" | "[" expr "," expr "]" ;
```

## Constructs

| construct | meaning | lowers to |
|---|---|---|
| `package p @v` | a versioned module | origins `axiom:p` |
| `import p` | load package `p` (`p/q.ov` next to the file, then the standard library) | — |
| `type T extends U { f: F }` | an entity sort with typed, unit-aware fields | each field is a functional predicate `T.f(x, v)` |
| `predicate p(x: T) world open\|closed` | a relation and its unknown policy (open by default) | `world p closed.` |
| `predicate f(x: T) -> U` | a functional relation: one value per input | `f(x, v)` plus a clash rule (below) |
| `predicate f(x: T) -> {U, U}` | outputs form an unordered tuple; `-> {U}` is set-valued | `f(x, a, b)` plus a swap rule |
| `function c(x: T) -> U [unordered]` | a term constructor (data, not a relation). `unordered` sorts its arguments | compound term `c(...)` |
| `entity a, b: T [= expr]` | constants; with `= expr`, a name for a structure | symbol `a`, or the structure itself |
| `axiom n(params): body -> heads` | a rule; packages only. No `->`: the conjunction is stated outright | one rule per head (a fact if ground) |
| `transformation n(...) requires B ensures E` | a reusable step: `B` premises, `E` conclusions | like an axiom |
| `controller n(...) { pipe a -> b; guard g }` | orders and guards transformations. It never adds truths | each listed transformation fires only with the guard as an extra premise |
| `generator g(x: T) yields U from p(x)` | a finite candidate domain drawn from a **closed** set-valued predicate | used by `generator X from g(...)` |
| `scenario s uses p extends t { ... }` | a context: the packages' axioms plus local entities, facts, assumptions | one RawOV program |
| `fact lit` | a stated fact (`fact:<scenario>`) | a fact, or a check rule |
| `assume n: lit` | a named hypothesis | a fact with origin `assume:n` |
| `query ...`, `expect ...` | an inline query and its expected verdict | a query rule; checked by the runner |
| `test n { ... }` | scenarios, queries and expectations | run by the runner and by pytest |
| `target n { must ...; prefer ... }` | an input for OVProver | parsed and checked; used in Milestone 6 |

**Statements** (`lit`):
- `p(args)`: an atom.
- `not p(args)`: for an **open** predicate this means `neg p` is derived;
  for a **closed** predicate, that `p` is not derivable. In a conclusion it
  always means `neg p`.
- `lhs = rhs`, `!=`, `<`, `<=`, `>`, `>=`: equations and comparisons.
- `x in s`: membership. With `[a, b]` it is an interval test; otherwise it is
  the package's `member(s, x)` predicate.
- `f(x) -> {C, D}` (facts only): the outputs of `f` on `x`.

**Values.** `b.mass` is a field. `f(x)` is a functional predicate's value
inside an expression (`major(add(B, HBr)) = ?p`), a constructor term, or one
of the built-ins `abs`, `min`, `max`, `canonical`.

## Native math

- **Exact rationals.** All numbers use `fractions.Fraction`; there is no
  rounding anywhere in the kernel path.
- **Units.** Every quantity carries a dimension vector over kg, m, s, A, K,
  mol, cd, plus USD for money. It is stored in base units, so `500 g` and
  `0.5 kg` are the same term.

  | units | |
  |---|---|
  | mass | kg g mg t |
  | length | m cm mm km |
  | time | s ms min h |
  | base | A K mol cd |
  | derived | N J kJ W kW Pa kPa C V Ω ohm Hz |
  | volume | L mL |
  | money | USD |

  Quantity types for fields and parameters: Number, Mass, Length, Time,
  Current, Temperature, Amount, Luminosity, Area, Volume, Velocity, Accel,
  Force, Momentum, Energy, Power, Pressure, Charge, Voltage, Resistance,
  Frequency, Molarity, MolarMass, Money.
- **`=` is an equation.**
  - In a premise it binds the one unknown variable (solving when needed) or,
    if all are bound, compares.
  - In a conclusion, every *slot* (field or functional call) that can be
    solved for gets its own rule. A slot can be solved for when it occurs
    once under `+ - * /` and unary minus. `F = b.mass * b.accel` gives two
    rules, one deriving `mass` and one deriving `accel`.
  - Nonlinear equations (`b.v ^ 2 = 4`) are error E402 until the sympy plugin
    (Milestone 2).
- **Builtins fire only when their inputs are bound.** The safety check (E403)
  reports any rule that would compute with an unbound variable.
- **`unknown`** as a value (`fact x.mass = unknown`) states nothing. This is
  the explicit "do not guess".

## Unknowns and candidate elimination

A scenario may talk about entities whose identity is not given:

```ov
scenario q11 uses chem.organic {
  generator A, B from isomers(C5H10)
  fact   ozonolysis(A) -> {C, D}
  fact   not tautomerizes(D)
  fact   grignard_alcohol(C) = tertiary
  fact   2-chloropentane in add(B, HCl)
  assume single_major: has_single_major(add(B, HBr, peroxide))

  query FIND ?A, ?C, ?D
  query FIND ?p WHERE major(add(B, HBr, peroxide)) = ?p
  query PROVE optically_active(add(C, HCN))
  query WHAT IF RETRACT not tautomerizes(D) THEN FIND ?A
}
```

**Where unknowns come from.** `A` and `B` come from a generator. `C` and `D`
are introduced by the arrow: they are whatever ozonolysis of `A` produces.

**How lowering solves for them.**
1. Unknowns linked by a statement form a component, here `{A, C, D}` and
   `{B}`. Each component gets a candidate relation: every combination the
   generators and arrows allow.
2. Every other statement about the unknowns *eliminates* the candidates for
   which its contradiction is **derived**:
   - `not tautomerizes(D)` eliminates the candidates where `tautomerizes(D)`
     is proven.
   - `grignard_alcohol(C) = tertiary` eliminates those where another value is
     proven.
   - `2-chloropentane in add(B, HCl)` eliminates those where it is not a
     product. `member` is closed-world, so "not a product" is a sound
     conclusion.
   - An `assume` eliminates only under its assumption. So the answer that
     depends on it carries the assumption in its label.
3. A value is **PROVEN** only when exactly one candidate survives and the
   generator is complete. With several survivors the query is **UNKNOWN**
   (`missing_facts`) and the runner lists the candidates. With none the
   scenario is **INCONSISTENT**.

**Queries.** A query that mentions an unknown uses its proven unique value.
`WHAT IF RETRACT <statement>` repeats a `fact` or `assume` exactly:
- retracting an assumption is a label lookup (no re-run);
- retracting a fact re-runs the program without it.

The reference answers:

| query | answer |
|---|---|
| FIND ?A, ?C, ?D | PROVEN: A = 2-methylbut-1-ene, C = butanone, D = methanal, no assumptions |
| FIND ?p | PROVEN: 1-bromopentane, under `{single_major}` |
| PROVE optically_active(add(C, HCN)) | REFUTED: a stereocentre, but racemic |
| WHAT IF RETRACT ... THEN FIND ?A | UNKNOWN: A ∈ {2-methylbut-1-ene, 2-methylbut-2-ene} |

## Facts that are not atoms

**Atom-like facts become RawOV facts.** That covers `fact p(a)`,
`fact not p(a)`, `fact x.f = v` and `fact a in s`.

**Any other fact becomes a check.** For example, `fact c.mass > 3 kg`:
- It lowers to a rule deriving `neg ov.consistent(<id>)` whenever the
  statement's contradiction is derived.
- A violated check therefore makes the scenario INCONSISTENT, with the
  responsible facts in the conflict set.

**Functional predicates and fields clash on different values.** Each gets a
rule deriving `neg f(x, v2)` when `f(x, v1)` and `f(x, v2)` with `v1 ≠ v2`
are both derived. So a stated mass that disagrees with the mass `newton2`
derives is reported as INCONSISTENT, never silently overwritten.

## Concept classes (the object layer)

A `fact type` is a class defined by its invariants. Its instances are the
values of its properties that satisfy every invariant, its own and its
ancestors'. `examples/geometry/square.ov` is the brief's example:

```ov
type Point { x: Real, y: Real }          # a record: every field is a quantity

fact type Quadrilateral { property vertices: Set<Point>  invariant four: count(vertices) = 4 }

fact type Square extends Quadrilateral {
  invariant shape: exists v in cycles(vertices):
                     all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0
                     all i: angle(v[i-1], v[i], v[i+1]) = 90 deg
  theorem diagonals_equal: exists v in cycles(vertices): dist(v[0], v[2]) = dist(v[1], v[3])
}
```

- **Properties** are typed: quantities, records (`Point`), `Set<T>`, `List<T>`.
  Tuples `(3, 1)` are record values, in field order.
- **Invariants** are the definition and are trusted. **Theorems** are claims:
  the runner proves each one from the invariants (see below) and reports
  PROVEN, REFUTED with a counterexample, or UNPROVEN.
- **`extends`** may name several parents. A shared ancestor's invariants are
  included once (the diamond rule): `Square extends Rectangle, Rhombus` in
  `math.geometry` has `Quadrilateral.four` and `Parallelogram.bisect` once each.
- **Quantifiers.** `exists v in C: ...`, `none v in C: ...` (no element
  satisfies it) and `all v in C: ...` range over a collection; their body
  runs to the end of the enclosing body, so they come last. `all i: chain`
  (no `in`) ranges over the indices of the list the chain indexes with `i`.
  Indices wrap around: `v[i+1]` of the last element is the first.
- **Implication.** `P -> Q` inside a body: `all v in cycles(s): <shape of v>
  -> <property of v>`.
- **Generators** introduce order into sets: `cycles(s)` and `orderings(s)`
  (every ordering), `subsets(s, k)`, `pairs(s)`.
- **Functions:** `count`, `dist`, `dist2` (squared distance), `angle(a, b, c)`
  (at b, in degrees), `abs`, `min`, `max`, and arithmetic on numbers.
- **Exactness.** Everything stays rational. `dist` comparisons are squared;
  `angle(...) = θ deg` is decided on the dot product for the angles whose
  cosine squared is rational (0, 30, 45, 60, 90, 120, 135, 150, 180). Other
  comparisons are rejected with E405. Write `dist2` for arithmetic on
  distances (Pythagoras: `dist2(a, c) = dist2(a, b) + dist2(b, c)`).
- **Do not write theorems with `exists` over an invariant's generator.**
  `exists v in cycles(s): P(v)` may pick any ordering. "The diagonals are
  equal", written that way, holds for every rhombus, by choosing an ordering
  that pairs up sides; the brief's own `Square.diagonals_equal` did this.
  Warning W202 flags it. Say that every ordering with the defining shape has
  the property: `all v in cycles(s): <shape of v> -> <property of v>`, or
  `none v in cycles(s): <shape of v> <property of v fails>`.

### Object queries

| query | answer |
|---|---|
| `FIND ?p: Point WHERE Square{vertices = {(3,1), (1,3), (5,3), ?p}} [LIMIT n]` | every solution (default limit 16), each re-checked |
| `PROVE UNIQUE ?p [WHERE ...]` | PROVEN if blocking the solution leaves no other; REFUTED with two witnesses; without WHERE it reuses the FIND before it |
| `COUNT ?p WHERE ...` | the exact number of solutions, or UNKNOWN(budget) past 4096 |
| `CHECK T1{...} IS T` | PROVEN, or REFUTED naming the invariants the instance fails |
| `COUNTEREXAMPLE T.theorem` | the theorem's verdict: REFUTED with a checked counterexample, PROVEN if its negation is unsat, UNKNOWN otherwise |

A pattern `T{field = value, ...}` is a partial instance: `?x` and unspecified
fields are unknowns (`Point{x = 3}` leaves `y` open). A set with unknown
elements is split into cases by which elements coincide, so `{(3,1), ?p}` has
one element when `?p = (3,1)`.

Every answer follows the same steps, all printed by `--verbose`:

1. **solve:** the invariants become polynomial constraints and z3 searches for
   a model (untrusted);
2. **re-check:** the model is substituted and every invariant is decided by the
   exact evaluator `raw/formula.py` (trusted, ~150 lines, no solver). A model
   that fails is never reported: the answer becomes UNKNOWN(plugin_unknown);
3. **block and re-solve** (FIND, UNIQUE, COUNT): found solutions are excluded
   and z3 asked again. Unsat ends the search. Unsat cannot be checked by
   substitution, so it is confirmed in a fresh solver, and the trace says so.

A query whose class has no instance at all is REFUTED with a minimal set of
invariants that conflict.

**Trust base.** Every verdict says what it rests on, like Lean's
`#print axioms`: `kernel` (the trusted evaluator re-checked an instance, or
the checker accepted a rule trace) and `z3_unsat` (an unsat answer only the
solver vouches for: UNIQUE, COUNT, a class with no instance, a proven
theorem). A proven theorem also lists the solver reductions its unsat was
computed under, as `red:fix_order`, `red:no_invariants`, `red:drop_implied`,
`red:translate` and `red:inherit` (docs/SEMANTICS.md §7). `--no-reductions`
turns them all off. `ov run --strict` turns every verdict that rests on
`z3_unsat` into UNKNOWN(plugin_unknown). A FIND keeps its re-checked bindings but no longer
claims the list is complete. Under `--strict`, W201 becomes error E208.

### Class checks

For every class in the file it runs, the runner checks:

- **consistency:** the invariants have an instance (PROVEN, with a re-checked
  witness), or INCONSISTENT with the conflicting invariants (an empty class);
- **each theorem:** no instance satisfies the invariants and violates the
  theorem (PROVEN, unsat confirmed by a fresh solver), or REFUTED with a
  counterexample that the evaluator confirms, or UNPROVEN.

Both use a *generic instance*: fresh unknowns in every slot, with collection
sizes taken from `count(p) = n` invariants. A class with an unbounded
collection gets UNPROVEN, not a guess. A theorem that states, word for word,
a theorem an ancestor proved is inherited.

Before solving, a theorem check applies only reductions that lose no model,
each printed in the trace:

- **counterexample ordering:** the counterexample's vertex ordering is fixed,
  because the generic set's elements are interchangeable unknowns;
- **implied invariants:** an invariant implied by the counterexample's
  conditions is left out;
- **translation:** one point is pinned to 0 in each coordinate where every
  polynomial is unchanged when all points shift together (checked exactly);
- **invariants last:** the negated theorem is first tried without the
  invariants, which proves the stronger statement when it is unsat.

Refuted theorems and empty classes make the runner exit with status 1.

**Lemmas.** If z3 can settle a theorem neither way from the invariants, the
check is retried with every theorem already PROVEN in the class or its
ancestors as an extra hypothesis. This is sound because each holds on every
instance. The answer lists the lemmas it used, and its trust base includes
theirs. An UNPROVEN theorem is never used.

### Axiom kinds (for `ov audit`)

Every assumption a package makes says what kind it is. All kinds lower the
same way; the kind is what `ov audit` reports.

| where | keyword | kind |
|---|---|---|
| package rule | `axiom` | foundation |
| package rule | `law` | an empirical law of nature (Newton's second law) |
| package rule | `definition` | a definition (momentum, molarity) |
| class member | `invariant` | a definition: a class is defined by its invariants |
| class member | `law` | an empirical law holding on the class (`law newton2: F = m * a`) |
| class member | `theorem`, `lemma` | must be proven by `ov check`; `lemma` marks a helper |

The built-in mathematics are the foundations. `ov audit` lists the ones a
package uses:
- ordered-field arithmetic;
- coordinates and the distance formula;
- angles via the dot product;
- polynomial integral and derivative;
- finite sets and generators.

### Quantities and calculus in classes

- **Properties may have quantity types** (`property v: Velocity`).
  - Class formulas and pattern values are dimension-checked when the class
    compiles (E301). A bare `0` matches any dimension.
  - Inside the solver and the evaluator, values are base-SI magnitudes.
  - Unknowns of a quantity type print with their unit: `?s = 21 m`.
- **`integral(e, t)`** is the integral of `e` from 0 to the value of the
  property `t`. **`deriv(e, t)`** is de/dt at that value.
  - `e` must be a polynomial in `t`; other properties are constants.
  - The trusted evaluator decides both exactly: it samples `e` at
    t = 0..degree, recovers the coefficients, and integrates or
    differentiates.
  - The units are those of `e` times (or divided by) those of `t`.

**Composition.** A property may be typed by another class, or be a `Set` or
`List` of one:
- `property b1: ConstantForce`;
- `property parts: List<Sample>` with `count(parts) = 2`.

Its value is a record of that class's properties. Fields are read with `.`
(`b1.v`, `parts[0].n`) and given in patterns
(`b1 = ConstantForce{ m = 2 kg, v = ?v }`). The class's invariants hold for
every component instance.
- They are added to the owner, named `Comp.inv@Owner.prop`, so `ov audit`
  counts them under the component, not as new definitions.
- A wrong component value is rejected by the trusted evaluator, naming the
  instantiated invariant.
- In calculus, the variable may be a component's property: `integral(a, t)`
  inside `ConstantForce` stays exact when the body is `b1`.

**Exact square roots.** `dist`, `sqrt(x)` (x rational) and solver answers that
are degree-2 algebraic numbers are exact surds: sums of rational multiples of
√k, with k squarefree.
- Arithmetic and equality are exact: different squarefree roots are linearly
  independent over the rationals.
- The sign is found by tightening bounds until they exclude 0.
- Examples: `x * x = 2` gives `x = ±√2`. The equilateral-triangle vertex is
  `(1, √3)`. `dist(A, P) + dist(P, B) = dist(A, B)` is proven for the section
  point.
- A nested root (√(2 + √3)) is compared only, by its square.

**Trigonometry (symbolic).** `property theta: Angle` is the pair (cos, sin) with
the foundation axiom cos² + sin² = 1. `sin(theta)` and `cos(theta)` read it.
- In a pattern, `theta = 30 deg` is exact at the special angles: 0, 30, 45,
  60, 90, 120, 135, 150 and 180 deg.
- Other angles take the problem's given values:
  `theta = Angle{ cos = 4/5, sin = 3/5 }`.
- `tan` is not provided: write `sin(x) = t * cos(x)`.

**exp, ln, pi and numeric answers.** `exp(x)` and `ln(x)` (x dimensionless) and
`pi` may appear in class formulas.
- **In proofs,** each is an opaque positive number, so a theorem proven for
  every such value holds for the true one:
  - `exp(u)` is an atom `e` with `e > 0`;
  - `ln(u)` is `L` with `exp(L) = u` and `u > 0`;
  - pi is bounded between 3.14159265358979 and 3.14159265358980.
- **Derivatives** follow the chain rule for `exp`: `deriv(N0 * exp(-k * t), t)`
  proves the rate law by differentiating the solution. Integrating, or
  differentiating `sqrt` or `ln` of the variable, is refused: treating them as
  constants would be unsound.
- **A FIND the exact solver cannot settle** is answered in numeric mode.
  1. Each unknown takes its value from its definition `p = E`, in invariant
     order.
  2. The trusted checker (`raw/numeric.py`) encloses `E` with rigorous
     interval arithmetic (`raw/interval.py`: Taylor series with remainder
     bounds, outward rounding). It accepts only:
     - one definition per interval property;
     - definitions that use earlier ones;
     - all other invariants decided strictly.
  3. `PROVEN ?N = 606.5306597 (± 1.8e-56)` then means the true value lies in
     that interval.
- **`tolerance x`** in a scenario bounds that relative half-width. The default
  is 1e-12. A wider enclosure is UNKNOWN(precision). `tolerance` used to be
  E207.

`physics.mechanics` defines velocity and displacement this way and proves
SUVAT from them:

```ov
fact type ConstantAcceleration {
  property u: Velocity
  property a: Accel
  property t: Time
  property v: Velocity
  property s: Length
  invariant elapsed: t >= 0
  invariant velocity: v = u + integral(a, t)
  invariant displacement: s = integral(u + integral(a, t), t)
  theorem suvat_timeless: v * v = u * u + 2 * a * s
}
```

## Error codes

Every diagnostic has a file, line and column, a caret under the offending
text, and a one-line hint. `tests/v1/test_lang.py` checks each code with its
exact span.

| code | meaning |
|---|---|
| E101 | unexpected token (the message lists what was expected) |
| E102 | unexpected character |
| E103 | unknown unit |
| E201 | unknown name, predicate, function, scenario or transformation |
| E202 | declared more than once (or a parameter shadows a declared name) |
| E203 | package not found, or the file does not declare that package |
| E204 | unknown field |
| E205 | wrong number of arguments |
| E206 | construct not allowed here (axioms outside packages, a predicate used as a value, ...) |
| E207 | not supported yet (`derived`); `import state` and `tolerance` are supported |
| E301 | dimension mismatch (`2 kg + 1 m`, `expected Mass, got Length`) |
| E302 | type mismatch |
| E303 | arithmetic or ordering on something that is not a quantity |
| E304 | a number followed by a name that is both a unit and a property (`p > 0 t > 0` reads `0 t` as zero tonnes); separate the conditions or write `(0) t` |
| E401 | a conclusion has nothing to derive |
| E402 | an equation cannot be solved syntactically (nonlinear: sympy plugin, M2) |
| E403 | a lowered rule is unsafe (a variable is used before it is bound) |
| E404 | a generator does not draw from a closed set-valued predicate |
| E405 | a class formula the exact evaluator cannot decide (an angle other than 0, 30, 45, 60, 90, 120, 135, 150, 180 deg; a distance inside arithmetic) |
| E406 | a class inherits from itself |
| E407 | a query names a lemma (`COUNTEREXAMPLE C.lemma`); a lemma serves only its own package's proofs, so anything a scenario, a query or another package relies on must be a `theorem` |
| E208 | an undeclared type under `--strict` (W201 otherwise) |
| E209 | an imported OVState is refused: tampered (hash mismatch), not canonical (unsorted, non-ground atoms), or unreadable |
| W201 | warning: an undeclared type is used and treated as an opaque entity type |
| W202 | warning: a theorem says `exists` over the same generator as an invariant, so it may be vacuous |

`ov audit PACKAGE` prints a package's axioms by kind (foundation, law,
definition), its theorems with status and trust base, the axiom ratio, and
with `--dag THEOREM` the theorem's dependencies down to axioms.

## Standard packages (Milestone 1)

| package | contents |
|---|---|
| `math.core` | shared vocabulary only. The arithmetic is native; Milestone 5 adds linear systems, divisibility, parity and induction |
| `physics.mechanics` | `Body` with mass and acceleration, `net_force`, Newton's second law |
| `math.geometry` | `Point`; Triangle, RightTriangle, Quadrilateral, Parallelogram, Rectangle, Rhombus, Square (diamond), Circle, OnCircle; theorems Pythagoras, opposite sides, equal and perpendicular diagonals, diagonal length, all proven; 13 tests |
| `chem.organic` | structures (substituent trees), C5H10 isomers, ozonolysis, tautomerism, Grignard alcohols, HX addition with Markovnikov/peroxide regioselectivity, HCN addition, stereocentres, racemic mixtures; 10 tests |

[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) lists what the language does
not do yet.

## Integers and counting (D-027)

- `property n: Integer` is a whole number: the class gets the type-derived
  invariant `Integer.whole@C.n` (the trusted evaluator checks the value is an
  integer; the solver uses `IsInt`).
- `mod(a, b)` is `a - b * floor(a / b)` (b a positive integer constant in solver
  queries); divisibility is `mod(b, a) = 0`.
- `COUNT` enumerates at most 4096 solutions (a deterministic budget); past it the
  answer is UNKNOWN(budget). Counting uses one incremental solver with a
  blocking clause per model; every model is re-checked by the kernel, and the
  count's completeness is the solver's final unsat (trust `z3_unsat`).
- Counting occurrences in a finite sequence is written with polynomial
  indicators over the finite alphabet (see `benchmarks/exams/jee2025/
  jee2025-math-p1q10`); there is no `count_of` builtin yet.

## For-all statements and ODE solutions (D-027)

- A theorem's properties are universally quantified, so a theorem such as
  `a * a + b * b + c * c >= a * b + b * c + c * a` is a for-all statement. It
  reaches `{kernel}` with a sum-of-squares certificate: squares with constant
  weights, or squares weighted by stated positive hypotheses (`m1 > 0`). The
  untrusted finder tries one square, the exact LDL decomposition of a
  quadratic's Gram matrix, and a factorisation into positive hypotheses times a
  square.
- `value_at(E, t, c)` is E with the property t set to c. A closed-form ODE
  solution y(t) is verified by two theorems: `deriv(y(t), t) = F(t, y(t))`
  (checked in the trusted ring of polynomials in t and exp atoms) and
  `value_at(y(t), t, t0) = y0`. Solving an ODE is not supported (v6); the
  solution must be proposed.

## Sums and induction (gap e)

- `sum(E, i, n)` is E summed over the new index i = 1..n. For a whole n up to
  10,000 the evaluator sums directly.
- A closed form `sum(E, i, n) = F(n)` is proved for every natural n by an
  induction certificate: the hypotheses must state `n: Integer` and `n >= 0`,
  and the checker verifies F(0) = 0 and F(n) - F(n-1) = E(n) by exact normal
  form (E may not mention n).
- A false closed form is refuted by a counterexample among small natural
  numbers, each decided by the evaluator.
