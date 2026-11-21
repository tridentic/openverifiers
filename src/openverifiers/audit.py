"""``ov audit``: what a package rests on (like Lean's ``#print axioms``).

    ov audit PACKAGE|FILE [--dag THEOREM ...] [--json]

For one package it lists:

- **axioms by kind**
  - *foundation*: the built-in mathematics its formulas use (ordered-field
    arithmetic, coordinates and distance, polynomial calculus, finite sets) and
    rule axioms declared with ``axiom``;
  - *law*: empirical laws (``law``, rule or class member);
  - *definition*: ``definition`` rules and class invariants (a class is
    defined by its invariants);
- **theorems** (``theorem`` and ``lemma``), each with its status (PROVEN,
  REFUTED or UNPROVEN) and ``trust_base``;
- the **axiom ratio**, axioms / (axioms + theorems);
- with ``--dag``, a theorem's dependencies down to axioms. They are found by
  deletion: a premise is dropped if the theorem is still proven without it.
  Each trial has a shorter time limit, so a premise kept only because a trial
  timed out makes the set larger than minimal, never wrong.

UNPROVEN theorems are listed, never used as lemmas, and so never support a
PROVEN answer. Untrusted tooling: it reports, it decides nothing.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .lang import ast as A
from .lang.check import STDLIB, Env, load
from .lang.errors import OVError
from .objects.compile import generic
from .objects.engine import ObjAnswer, Settings, _Run, check_classes, theorem
from .raw.formula import ClassDef, Unsupported
from .raw.program import Span
from .raw.terms import Compound, Str, Term

USAGE = "usage: ov audit PACKAGE|FILE [--dag THEOREM ...] [--json]"

#: built-in function symbol -> the foundation it rests on
FOUNDATIONS = {
    "+": "ordered-field arithmetic", "-": "ordered-field arithmetic",
    "*": "ordered-field arithmetic", "/": "ordered-field arithmetic",
    "^": "ordered-field arithmetic", "f.cmp": "ordered-field arithmetic",
    "abs": "ordered-field arithmetic", "min": "ordered-field arithmetic",
    "max": "ordered-field arithmetic",
    "f.dist": "coordinates and the distance formula",
    "f.dist2": "coordinates and the distance formula",
    "f.angle": "angles via the dot product",
    "f.integral": "polynomial integral and derivative",
    "f.deriv": "polynomial integral and derivative",
    "f.count": "finite sets and generators", "f.cycles": "finite sets and generators",
    "f.orderings": "finite sets and generators", "f.subsets": "finite sets and generators",
    "f.pairs": "finite sets and generators",
}


@dataclass
class Item:
    name: str
    kind: str                  # foundation | law | definition | axiom | theorem
    status: str = ""           # theorems: PROVEN | REFUTED | UNPROVEN
    trust: list[str] = field(default_factory=list)
    where: str = ""
    note: str = ""             # why a declared definition was reclassified as an axiom


@dataclass
class Report:
    package: str
    file: str
    axioms: list[Item]
    theorems: list[Item]
    dags: dict[str, Any] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        n = len(self.axioms) + len(self.theorems)
        return len(self.axioms) / n if n else 0.0

    @property
    def claim_ratio(self) -> float:
        """(foundation + law + axiom) / (those + theorems): conservative definitions add
        no trust, so they are left out (CTO, M-CAP item 3)."""
        claims = sum(a.kind in ("foundation", "law", "axiom") for a in self.axioms)
        n = claims + len(self.theorems)
        return claims / n if n else 0.0

    @property
    def strict_claim_ratio(self) -> float:
        """As claim_ratio, but a class invariant counts as a definition only when it is
        `p = E` defining one property non-circularly."""
        claims = sum(a.kind in ("foundation", "law", "axiom") or bool(a.note)
                     for a in self.axioms)
        n = claims + len(self.theorems)
        return claims / n if n else 0.0

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.axioms:
            out[a.kind] = out.get(a.kind, 0) + 1
        return out


def _functors(t: Term, out: set[str]) -> set[str]:
    if isinstance(t, Compound):
        out.add(t.functor)
        for a in t.args:
            _functors(a, out)
    return out


def resolve(arg: str) -> Path:
    p = Path(arg)
    if p.suffix == ".ov":
        return p
    return STDLIB / Path(*arg.split(".")).with_suffix(".ov")


def _own_classes(env: Env, file: str) -> list[str]:
    return [n for n, d in env.class_decls.items() if d.span.file == file]


def audit(path: Path, dag: Sequence[str] = (), st: Settings | None = None) -> Report:
    st = st or Settings()
    env = load(path)
    file = str(path)
    mod = env.main
    pkg = mod.package.name if mod.package else "<main>"
    axioms: list[Item] = []
    heads: dict[str, int] = {}
    for it in mod.items:
        if isinstance(it, A.Axiom):
            for h in it.head:
                for name in _lit_preds(h):
                    heads[name] = heads.get(name, 0) + 1
    for it in mod.items:
        if isinstance(it, A.Axiom) and it.kind == "axiom":
            item = Item(it.name, it.basis, where=f"{Path(file).name}:{it.span.line}")
            if it.basis == "definition":
                why = _rule_not_conservative(it, heads)
                if why:
                    item.kind, item.note = "axiom", why
            axioms.append(item)
        elif isinstance(it, A.Axiom):           # a transformation: a defined step
            axioms.append(Item(it.name, "definition", where=f"{Path(file).name}:{it.span.line}"))
    mine = _own_classes(env, file)
    objs = env.objects
    used: set[str] = set()
    for c in mine:
        cd = objs.defs.get(c)
        if cd is None:
            continue
        for n, f in (*cd.invariants, *cd.theorems):
            if n.split(".")[0] == c:
                _functors(f, used)
        defs = _definition_targets(cd)
        for n, f in cd.invariants:
            if n.split(".")[0] == c:
                item = Item(n, "law" if objs.kinds.get(n) == "law" else "definition",
                            where=_where(objs.spans.get(n)))
                if item.kind == "definition":
                    # Conservative at the class level: the class is a new symbol defined by
                    # its invariants over its own properties (non-circular: E406). The
                    # stricter per-equation reading is kept as a note and a second ratio.
                    item.note = _not_conservative(n, f, defs)
                axioms.append(item)
    founds = sorted({FOUNDATIONS[f] for f in used if f in FOUNDATIONS})
    axioms = [Item(f, "foundation", where="built in") for f in founds] + axioms
    checks = check_classes(objs, set(mine), st) if mine else []
    status = {a.title.removeprefix("theorem "): a for a in checks if a.kind == "theorem"}
    theorems = []
    for c in mine:
        cd = objs.defs.get(c)
        for n, _ in (cd.theorems if cd else ()):
            a = status.get(n)
            v = "UNPROVEN" if a is None or a.verdict == "UNKNOWN" else a.verdict
            theorems.append(Item(n, objs.kinds.get(n, "theorem"), v,
                                 sorted(a.trust_base) if a else [], _where(objs.spans.get(n))))
    rep = Report(pkg, file, axioms, theorems)
    for name in dag:
        rep.dags[name] = _dag(env, name, status, st, set())
    return rep


def _lit_preds(x: object) -> set[str]:
    out: set[str] = set()
    if isinstance(x, A.Call):
        out.add(x.fn)
    if isinstance(x, tuple):
        for i in x:
            out |= _lit_preds(i)
    elif hasattr(x, "__dataclass_fields__"):
        for f in x.__dataclass_fields__:
            if f != "span":
                out |= _lit_preds(getattr(x, f))
    return out


def _rule_not_conservative(it: A.Axiom, heads: dict[str, int]) -> str:
    """A `definition` rule is conservative when each predicate it concludes is
    concluded by no other rule and does not occur in its own body (non-recursive)."""
    hp = set().union(*(_lit_preds(h) for h in it.head)) if it.head else set()
    if any(heads.get(p, 0) > 1 for p in hp):
        return "its predicate is concluded by more than one rule"
    if hp & _lit_preds(it.body):
        return "recursive: it uses the predicate it defines"
    return ""


def _target(f: Term) -> tuple[str, Term] | None:
    """`p = E` with p a property: (p, E)."""
    if isinstance(f, Compound) and f.functor == "f.cmp" and f.args[0] == Str("="):
        lhs = f.args[1]
        if isinstance(lhs, Compound) and lhs.functor == "f.p" and isinstance(lhs.args[0], Str):
            return lhs.args[0].value, f.args[2]
    return None


def _definition_targets(cd: ClassDef) -> dict[str, list[tuple[str, Term]]]:
    out: dict[str, list[tuple[str, Term]]] = {}
    for n, f in cd.invariants:
        t = _target(f)
        if t is not None:
            out.setdefault(t[0], []).append((n, t[1]))
    return out


def _not_conservative(name: str, f: Term, defs: dict[str, list[tuple[str, Term]]]) -> str:
    """A class invariant is a conservative definition when it is `p = E` for a property
    p that no other invariant defines and that E does not depend on, even through other
    definitions (non-circular). Anything else constrains existing symbols: an axiom."""
    t = _target(f)
    if t is None:
        return "not of the form `property = expression`: it constrains existing symbols"
    p, e = t
    if len(defs.get(p, [])) > 1:
        return f"{p} is defined more than once"
    seen: set[str] = set()
    todo = list(_props(e))
    while todo:
        q = todo.pop()
        if q == p:
            return f"circular: {p} depends on itself"
        if q in seen:
            continue
        seen.add(q)
        for _, e2 in defs.get(q, []):
            todo += list(_props(e2))
    return ""


def _props(t: Term) -> set[str]:
    if isinstance(t, Compound):
        if t.functor == "f.p" and isinstance(t.args[0], Str):
            return {t.args[0].value}
        return {x for a in t.args for x in _props(a)}
    return set()


def _where(sp: Span | None) -> str:
    return f"{Path(sp.file).name}:{sp.line}" if sp is not None else ""


def needed(cls: ClassDef, th: tuple[str, Term], gen: dict[str, Term],
           premises: list[tuple[str, Term]], st: Settings) -> list[str]:
    """A minimal set of premises (invariants, laws, lemmas) the theorem is proven from,
    by deletion. Each trial is a full theorem check with a shorter time limit."""
    keep = list(premises)
    quick = replace(st, timeout_ms=max(1000, st.timeout_ms // 4))
    for p in list(keep):
        trial = [x for x in keep if x is not p]
        v, *_ = theorem(replace(cls, invariants=tuple(trial)), th, _Run(quick, []), [], gen)
        if v == "PROVEN":
            keep = trial
    return [n for n, _ in keep]


def _dag(env: Env, name: str, status: dict[str, ObjAnswer], st: Settings,
         seen: set[str]) -> dict[str, Any]:
    objs = env.objects
    cname = name.rpartition(".")[0]
    cd = objs.defs.get(cname)
    th = next((t for t in (cd.theorems if cd else ()) if t[0] == name), None)
    if cd is None or th is None:
        return {"name": name, "error": "unknown theorem"}
    a = status.get(name)
    node: dict[str, Any] = {"name": name, "kind": objs.kinds.get(name, "theorem"),
                            "status": "UNPROVEN" if a is None or a.verdict == "UNKNOWN"
                            else a.verdict,
                            "trust": sorted(a.trust_base) if a else []}
    if node["status"] != "PROVEN" or name in seen:
        return node
    seen.add(name)
    try:
        gen = generic(cd, objs.prop_types[cname], objs.records, objs.record_types)
    except Unsupported as e:
        node["error"] = str(e)
        return node
    if isinstance(gen, str):
        node["error"] = gen
        return node
    lemmas = [(n, f) for n, f in _proven_before(cd, name, status, objs.ancestors[cname],
                                                objs.defs)]
    deps = needed(cd, th, gen, [*cd.invariants, *lemmas], st)
    kids = []
    for d in deps:
        k = objs.kinds.get(d, "invariant")
        if k in ("theorem", "lemma"):
            kids.append(_dag(env, d, status, st, seen))
        else:
            kids.append({"name": d, "kind": "law" if k == "law" else "definition"})
    used: set[str] = set()
    _functors(th[1], used)
    for d in deps:
        for n, f in cd.invariants:
            if n == d:
                _functors(f, used)
    node["foundations"] = sorted({FOUNDATIONS[f] for f in used if f in FOUNDATIONS})
    node["uses"] = kids
    return node


def _proven_before(cd: ClassDef, name: str, status: dict[str, ObjAnswer],
                   ancestors: tuple[str, ...], defs: dict[str, ClassDef]
                   ) -> list[tuple[str, Term]]:
    """Proven theorems of the class (declared before ``name``) and of its ancestors."""
    out: list[tuple[str, Term]] = []
    for c in (*ancestors, cd.name):
        for n, f in defs[c].theorems if c in defs else ():
            if n == name:
                return out
            a = status.get(n)
            if a is not None and a.verdict == "PROVEN" and n.split(".")[0] == c:
                out.append((n, f))
    return out


# ---------------------------------------------------------------- printing


def render(rep: Report) -> str:
    c = rep.counts()
    out = [f"package {rep.package}  ({rep.file})", "",
           f"axioms: {len(rep.axioms)}  (foundation {c.get('foundation', 0)}, "
           f"law {c.get('law', 0)}, axiom {c.get('axiom', 0)}, "
           f"conservative definition {c.get('definition', 0)})"]
    for a in rep.axioms:
        note = f"  [strict reading: an axiom, {a.note}]" if a.note and a.kind == "definition" \
            else f"  [declared a definition, not conservative: {a.note}]" if a.note else ""
        out.append(f"  {a.kind:<10} {a.name}  {a.where}{note}")
    proven = sum(t.status == "PROVEN" for t in rep.theorems)
    out += ["", f"theorems: {len(rep.theorems)}  (PROVEN {proven}, "
            f"UNPROVEN {sum(t.status == 'UNPROVEN' for t in rep.theorems)}, "
            f"REFUTED {sum(t.status == 'REFUTED' for t in rep.theorems)})"]
    for t in rep.theorems:
        trust = "  trust {" + ", ".join(t.trust) + "}" if t.trust else ""
        mark = "" if t.status == "PROVEN" else "  <- not usable as a lemma"
        out.append(f"  {t.status:<9} {t.name}{trust}  {t.where}{mark}")
    claims = sum(a.kind in ("foundation", "law", "axiom") for a in rep.axioms)
    out += ["", f"axiom ratio: {len(rep.axioms)} / ({len(rep.axioms)} + {len(rep.theorems)})"
            f" = {rep.ratio:.2f}",
            f"claim ratio: {claims} / ({claims} + {len(rep.theorems)}) = {rep.claim_ratio:.2f}"
            "  (foundations, laws and non-conservative axioms; definitions add no trust)",
            f"strict claim ratio: {rep.strict_claim_ratio:.2f}  (a class invariant counts as a "
            "definition only if it is `p = E` defining one property)"]
    for name, d in rep.dags.items():
        out += ["", f"dependencies of {name}:"]
        out += _tree(d, "  ")
    return "\n".join(out)


def _tree(d: dict[str, Any], pad: str) -> list[str]:
    head = f"{pad}{d['name']}  [{d.get('kind', '')}"
    head += f", {d['status']}" if "status" in d else ""
    head += f", trust {{{', '.join(d['trust'])}}}" if d.get("trust") else ""
    head += "]"
    out = [head]
    if d.get("error"):
        out.append(f"{pad}  ({d['error']})")
    for k in d.get("uses", []):
        out += _tree(k, pad + "  ")
    if d.get("foundations"):
        out.append(f"{pad}  foundations: {', '.join(d['foundations'])}")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    dag: list[str] = []
    while "--dag" in args:
        i = args.index("--dag")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        dag.append(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    path = resolve(args[0])
    if not path.is_file():
        print(f"ov audit: no package file {path}", file=sys.stderr)
        return 2
    try:
        rep = audit(path, dag)
    except OVError as e:
        print(e.render(), file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"package": rep.package, "ratio": round(rep.ratio, 3),
                          "claim_ratio": round(rep.claim_ratio, 3),
                          "strict_claim_ratio": round(rep.strict_claim_ratio, 3),
                          "axioms": [a.__dict__ for a in rep.axioms],
                          "theorems": [t.__dict__ for t in rep.theorems],
                          "dags": rep.dags}, indent=2))
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
