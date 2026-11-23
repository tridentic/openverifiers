"""Re-check object-layer records (Condition B) against the compiled classes.

The engine (untrusted) leaves JSON records behind its kernel verdicts:
``model`` (an instance is a member of a class) and ``certificate`` (a part of
a theorem, or a uniqueness claim with its query's givens, has a certificate).
A uniqueness record's givens are filled in from the compiled query plan by the
caller (runner.recheck_records), not taken from the engine.
Here each record is decided again by the trusted evaluator and certificate
checker. Its invariants, theorem and hypotheses come from the compiled class
(``defs``), never from the record, so a record cannot weaken what it claims.
A lemma (a one-part theorem) may be used only after its certificate passed
earlier in the run.

Trusted code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..raw.canon import _unfrac as fr
from ..raw.canon import term_from_json as tj
from ..raw.certificate import Certificate, check
from ..raw.formula import ClassDef, Unsupported, failing
from ..raw.terms import Compound, Str, Term


def parts(f: Term, name: str) -> list[tuple[str, Term]]:
    """A formula's top-level comparisons (and integrality facts) as name, name#2, ..."""
    xs = list(f.args) if isinstance(f, Compound) and f.functor == "f.and" else [f]
    xs = [x for x in xs if isinstance(x, Compound) and x.functor in ("f.cmp", "f.isint")]
    return [(name if i == 0 else f"{name}#{i + 1}", x) for i, x in enumerate(xs)]


def _cert(c: Mapping[str, Any]) -> Certificate:
    return Certificate(tuple(c["factors"]), tuple((n, tj(x)) for n, x in c["coeffs"]),
                       tuple((fr(w), tj(x)) for w, x in c["squares"]),
                       tuple(map(tj, c["constants"])),
                       tuple((fr(w), tuple(ns), tj(x)) for w, ns, x in c["wsquares"]),
                       tuple(c["induction"]) if c["induction"] else None,
                       tuple(tuple((tj(k), tuple(ns), tj(q) if q else None) for k, ns, q in t)
                             for t in c.get("sums", [])),
                       tuple((tj(u), tj(k), tuple(ns), tuple(map(tj, xs)))
                             for u, k, ns, xs in c.get("positive", [])))


def check_records(records: Sequence[Mapping[str, Any]], defs: Mapping[str, ClassDef]
                  ) -> list[str]:
    """The records that fail (empty: all re-checked)."""
    bad, done, proven = list[str](), set[str](), {th: f for d in defs.values()
                                                   for th, f in d.theorems}
    for i, r in enumerate(records):
        try:
            cls = defs[r["class"]]
            hyps = {n: x for k, f in cls.invariants for n, x in parts(f, k)}
            if r["kind"] == "model":
                ok = failing(cls, {k: tj(v) for k, v in r["props"].items()}) == ()
            else:
                lemmas = r.get("lemmas", [])
                if not set(lemmas) <= done:
                    raise ValueError("a lemma not checked earlier in the run")
                hyps.update(h for lem in lemmas for h in parts(proven[lem], f"lemma:{lem}"))
                hyps.update((f"given:{k}", Compound("f.cmp", (Str("="), Compound(
                    "f.p", (Str(k),)), tj(v)))) for k, v in r.get("givens", {}).items())
                th = proven.get(r.get("theorem", ""), Compound("f.and", ()))
                goal = tj(r["goal"]) if "goal" in r else parts(th, "")[r["part"]][1]
                ok = check(goal, hyps, _cert(r["cert"]))
                done |= {r["theorem"]} if ok and len(parts(th, "")) == 1 else set()
        except (KeyError, IndexError, TypeError, ValueError, Unsupported):
            ok = False
        bad += [] if ok else [f"record {i} ({r.get('kind')}, {r.get('class')}) rejected"]
    return bad
