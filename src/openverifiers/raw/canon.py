"""Canonical JSON for RawOV terms, atoms and programs (W2.5).

The trusted path reads programs and traces only in this form, with the
standard library's ``json``: no text grammar is trusted. Every value has one
encoding, and decoding checks that the input is in that encoding (a number is
``"p/q"`` or ``"p"`` exactly as ``str(Fraction)`` writes it), so two equal
terms always have the same JSON text.

    term     ["sym", name] | ["str", s] | ["var", name]
             | ["num", "p/q", [[dim, "p/q"], ...]] | ["app", functor, [term, ...]]
    atom     {"pred": p, "args": [term, ...], "neg": bool}
    literal  ["pos", atom] | ["not", atom] | ["is", var, term] | ["cmp", op, term, term]
    span     [file, line, col, end_line, end_col] | null

The RawOV text form (``openverifiers.rawtext``) is an untrusted convenience.

Trusted code.
"""

from __future__ import annotations

from fractions import Fraction

from .program import (
    Assign,
    Atom,
    Compare,
    Domain,
    Fact,
    Literal,
    Naf,
    Pos,
    Program,
    Rule,
    Span,
    World,
)
from .terms import Compound, Num, Str, Sym, Term, Var


def _unfrac(s: object) -> Fraction:
    if not isinstance(s, str) or str(Fraction(s)) != s:
        raise ValueError(f"not a canonical rational: {s!r}")
    return Fraction(s)


def _s(x: object) -> str:
    if not isinstance(x, str):
        raise ValueError(f"expected a string, got {x!r}")
    return x


def _list(x: object) -> list[object]:
    if not isinstance(x, list):
        raise ValueError(f"expected a list, got {x!r}")
    return x


def _int(x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"expected an integer, got {x!r}")
    return x


def term_to_json(t: Term) -> list[object]:
    if isinstance(t, Sym):
        return ["sym", t.name]
    if isinstance(t, Str):
        return ["str", t.value]
    if isinstance(t, Var):
        return ["var", t.name]
    if isinstance(t, Num):
        return ["num", str(t.value), [[k, str(e)] for k, e in t.dims]]
    return ["app", t.functor, [term_to_json(a) for a in t.args]]


def term_from_json(d: object) -> Term:
    d = _list(d)
    tag = d[0] if d else None
    if tag in ("sym", "str", "var") and len(d) == 2:
        name = _s(d[1])
        return Sym(name) if tag == "sym" else Str(name) if tag == "str" else Var(name)
    if tag == "num" and len(d) == 3:
        rows = [_list(p) for p in _list(d[2])]
        dims = tuple((_s(p[0]), _unfrac(p[1])) for p in rows if len(p) == 2)
        if len(dims) != len(rows) or list(dims) != sorted(dims) or any(e == 0 for _, e in dims):
            raise ValueError(f"dimension vector not canonical: {d[2]!r}")
        return Num(_unfrac(d[1]), dims)
    if tag == "app" and len(d) == 3:
        return Compound(_s(d[1]), tuple(term_from_json(a) for a in _list(d[2])))
    raise ValueError(f"not a term: {d!r}")


def atom_to_json(a: Atom) -> dict[str, object]:
    return {"pred": a.pred, "args": [term_to_json(t) for t in a.args], "neg": a.neg}


def atom_from_json(d: object) -> Atom:
    if not isinstance(d, dict) or set(d) != {"pred", "args", "neg"} \
            or not isinstance(d["neg"], bool):
        raise ValueError(f"not an atom: {d!r}")
    return Atom(_s(d["pred"]), tuple(term_from_json(t) for t in _list(d["args"])), d["neg"])


def span_to_json(s: Span | None) -> list[object] | None:
    return None if s is None else [s.file, s.line, s.col, s.end_line, s.end_col]


def span_from_json(d: object) -> Span | None:
    if d is None:
        return None
    d = _list(d)
    if len(d) != 5:
        raise ValueError(f"not a span: {d!r}")
    return Span(_s(d[0]), *(_int(x) for x in d[1:]))


def _lit_to_json(lit: Literal) -> list[object]:
    if isinstance(lit, Pos | Naf):
        return ["pos" if isinstance(lit, Pos) else "not", atom_to_json(lit.atom)]
    if isinstance(lit, Assign):
        return ["is", lit.var.name, term_to_json(lit.expr)]
    return ["cmp", lit.op, term_to_json(lit.left), term_to_json(lit.right)]


def _lit_from_json(d: object) -> Literal:
    d = _list(d)
    if len(d) == 2 and d[0] in ("pos", "not"):
        return (Pos if d[0] == "pos" else Naf)(atom_from_json(d[1]))
    if len(d) == 3 and d[0] == "is":
        return Assign(Var(_s(d[1])), term_from_json(d[2]))
    if len(d) == 4 and d[0] == "cmp":
        return Compare(_s(d[1]), term_from_json(d[2]), term_from_json(d[3]))
    raise ValueError(f"not a literal: {d!r}")


def program_to_json(p: Program) -> dict[str, object]:
    return {
        "worlds": [[w.pred, w.closed] for w in p.worlds],
        "facts": [[f.id, atom_to_json(f.atom), f.origin, span_to_json(f.span)] for f in p.facts],
        "domains": [[d.id, d.pred, [term_to_json(a) for a in d.args],
                     [term_to_json(v) for v in d.values], d.complete, span_to_json(d.span)]
                    for d in p.domains],
        "rules": [[r.id, atom_to_json(r.head), [_lit_to_json(b) for b in r.body],
                   span_to_json(r.span)] for r in p.rules],
    }


def _rows(d: dict[str, object], key: str, width: int) -> list[list[object]]:
    rows = [_list(r) for r in _list(d[key])]
    if any(len(r) != width for r in rows):
        raise ValueError(f"malformed {key} entry")
    return rows


def program_from_json(d: object) -> Program:
    if not isinstance(d, dict) or set(d) != {"worlds", "facts", "domains", "rules"}:
        raise ValueError("a program has exactly: worlds, facts, domains, rules")
    worlds = []
    for pred, closed in _rows(d, "worlds", 2):
        if not isinstance(closed, bool):
            raise ValueError("world policy must be true/false")
        worlds.append(World(_s(pred), closed))
    facts = tuple(Fact(_s(i), atom_from_json(a), _s(o), span_from_json(s))
                  for i, a, o, s in _rows(d, "facts", 4))
    domains = []
    for i, pred, args, values, complete, s in _rows(d, "domains", 6):
        if not isinstance(complete, bool):
            raise ValueError("domain completeness must be true/false")
        domains.append(Domain(_s(i), _s(pred), tuple(map(term_from_json, _list(args))),
                              tuple(map(term_from_json, _list(values))), complete,
                              span_from_json(s)))
    rules = tuple(Rule(_s(i), atom_from_json(h), tuple(map(_lit_from_json, _list(b))),
                       span_from_json(s)) for i, h, b, s in _rows(d, "rules", 4))
    return Program(tuple(worlds), facts, rules, tuple(domains))
