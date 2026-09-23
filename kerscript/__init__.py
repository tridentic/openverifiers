"""KDScript — a data-first, domain-agnostic verification language.

Two languages, one compile target:

  * KDScript-Domain  — declarative, harness-authored. Defines units, typed
    facts, relations, transformations, guards, judged steps. NOT
    Turing-complete.
  * KDScript-Proof   — agent-facing trace language. Names registered
    transformations, supplies inputs, opens/closes assumption scopes. NOT
    Turing-complete.

Both compile into the existing OpenVerifiers v2 runtime (Registry,
Transformation dispatch, provenance tiers, proof/discharge engine). The
intermediate representation in `ir.py` is plain JSON-safe data: no Python
semantics leak into it, so the execution core underneath could be
reimplemented in another language without changing a single KDScript
document.

Package layout:

    kern/ir.py             DomainIR — pure-data records
    kern/units.py          unit tokens + dimension algebra (portable)
    kern/builtins.py       core logical primitives (cross-domain)
    kern/judged.py         judged-step seam + judge registry
    kern/domain_parser.py  KDScript-Domain text -> DomainIR
    kern/compiler.py       DomainIR -> v2 Grammar
    kern/proof_parser.py   KDScript-Proof text -> TraceStep list
    kern/export.py         regenerate opk/ from the Python grammars
"""

__version__ = "0.1.0"