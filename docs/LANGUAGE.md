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

This is the grammar in `src/openverifiers/lang/grammar.lark`. It is LALR(1),
with no conflicts. `{x}` means zero or more, `[x]` optional, `"..."` a keyword.

```ebnf
file        = { item } ;
item        = package | import | type | predicate | function | entity | axiom
            | transformation | controller | generator_decl | scenario | test
            | target | query | expect ;

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

params      = group { "," group } ;
group       = names ":" NAME [ "=" expr ] ;          (* a, b: Group *)
names       = NAME { "," NAME } ;
dotted      = NAME { "." NAME } ;

query       = "query" okql ;
okql        = "PROVE" lit
            | "FIND" QVAR { "," QVAR } [ "WHERE" conj ]
            | "WHAT" "IF" change { "AND" change } "THEN" okql ;
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
postfix     = atom { "." NAME } | NAME "(" [ expr { "," expr } ] ")" ;
atom        = NAME | QVAR | QUANTITY | STRING | "unknown" | "(" expr ")"
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
| W201 | warning: an undeclared type is used and treated as an opaque entity type |

## Standard packages (Milestone 1)

| package | contents |
|---|---|
| `math.core` | shared vocabulary only. The arithmetic is native; Milestone 5 adds linear systems, divisibility, parity and induction |
| `physics.mechanics` | `Body` with mass and acceleration, `net_force`, Newton's second law |
| `chem.organic` | structures (substituent trees), C5H10 isomers, ozonolysis, tautomerism, Grignard alcohols, HX addition with Markovnikov/peroxide regioselectivity, HCN addition, stereocentres, racemic mixtures; 10 tests |

[KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) lists what the language does
not do yet.
