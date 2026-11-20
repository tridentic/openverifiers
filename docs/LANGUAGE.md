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
if one fails. (`ov run` arrives in Milestone 3; full OKQL in Milestone 4.)

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
  - Because of this, `a-b` is one name. Write `a - b`, with spaces, to
    subtract. Error E201 points this out.
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

There are four shift/reduce conflicts, all inside class bodies, where
conditions are written one after another with no separator (as in the brief's
`Square`). Each is resolved as *shift*, so a condition extends as far as it
can: after a name, `(` starts a call, `{` a pattern, `[` an index, and `-`
continues a subtraction. Start each condition on a new line with a name, a
number or `all`. `tests/v1/test_objects.py` checks that these four are the
only conflicts.

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
fbody       = fsimple { fsimple } | { fsimple } fquant ;    (* conditions are conjoined *)
fquant      = ( "exists" | "none" ) NAME "in" expr ":" fbody ;
fsimple     = fchain | "all" NAME [ "in" expr ] ":" fchain | "not" fchain ;
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
  satisfies it) and `all x in C: ...`. `all i: ...` without `in` ranges over the
  indices of the list the body indexes with `i`. Indices wrap around: `v[i+1]`
  of the last element is the first, and `v[i-1]` works too.
- **Generators** introduce order into sets: `cycles(s)` and `orderings(s)`
  (every ordering), `subsets(s, k)`, `pairs(s)`.
- **Functions:** `count`, `dist`, `dist2` (squared distance), `angle(a, b, c)`
  (at b, in degrees), `abs`, `min`, `max`, and arithmetic on numbers.
- **Exactness.** Everything stays rational. `dist` comparisons are squared;
  `angle(...) = θ deg` is decided on the dot product for the angles whose
  cosine squared is rational (0, 30, 45, 60, 90, 120, 135, 150, 180). Other
  comparisons are rejected with E405. Write `dist2` for arithmetic on
  distances (Pythagoras: `dist2(a, c) = dist2(a, b) + dist2(b, c)`).
- **Write theorems with `none`.** `exists v in cycles(s): P(v)` may pick any
  ordering. "The diagonals are equal", written that way, holds for every
  rhombus, by choosing an ordering that pairs up sides. Say instead that no
  ordering with the defining shape lacks the property:
  `none v in cycles(s): <shape of v>  <property of v fails>`.

### Object queries

| query | answer |
|---|---|
| `FIND ?p: Point WHERE Square{vertices = {(3,1), (1,3), (5,3), ?p}} [LIMIT n]` | every solution (default limit 16), each re-checked |
| `PROVE UNIQUE ?p [WHERE ...]` | PROVEN if blocking the solution leaves no other; REFUTED with two witnesses; without WHERE it reuses the FIND before it |
| `COUNT ?p WHERE ...` | the exact number of solutions, or UNKNOWN(budget) past 64 |
| `CHECK T1{...} IS T` | PROVEN, or REFUTED naming the invariants the instance fails |
| `COUNTEREXAMPLE T.theorem` | PROVEN with a checked counterexample, or REFUTED (none exists) |

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
a theorem an ancestor proved is inherited. Refuted theorems and empty classes
make the runner exit with status 1.

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
| E207 | not supported until a later milestone (`import state`) |
| E301 | dimension mismatch (`2 kg + 1 m`, `expected Mass, got Length`) |
| E302 | type mismatch |
| E303 | arithmetic or ordering on something that is not a quantity |
| E401 | a conclusion has nothing to derive |
| E402 | an equation cannot be solved syntactically (nonlinear: sympy plugin, M2) |
| E403 | a lowered rule is unsafe (a variable is used before it is bound) |
| E404 | a generator does not draw from a closed set-valued predicate |
| E405 | a class formula the exact evaluator cannot decide (an angle other than 0, 30, 45, 60, 90, 120, 135, 150, 180 deg; a distance inside arithmetic) |
| E406 | a class inherits from itself |
| W201 | warning: an undeclared type is used and treated as an opaque entity type |

## Standard packages (Milestone 1)

| package | contents |
|---|---|
| `math.core` | shared vocabulary only. The arithmetic is native; Milestone 5 adds linear systems, divisibility, parity and induction |
| `physics.mechanics` | `Body` with mass and acceleration, `net_force`, Newton's second law |
| `math.geometry` | `Point`; Triangle, RightTriangle, Quadrilateral, Parallelogram, Rectangle, Rhombus, Square (diamond), Circle, OnCircle; theorems Pythagoras, opposite sides, equal and perpendicular diagonals, diagonal length, all proven; 13 tests |
| `chem.organic` | structures (substituent trees), C5H10 isomers, ozonolysis, tautomerism, Grignard alcohols, HX addition with Markovnikov/peroxide regioselectivity, HCN addition, stereocentres, racemic mixtures; 10 tests |

[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) lists what the language does
not do yet.
