"""OV-Paper hooks (v1 carries the data; the renderers are v3, MP §7 v3).

For each class theorem of a checked file, ``blueprints`` returns plain JSON:

- ``statement``: the theorem's source line, where it lives, and ``proposed_by``
  (``founder-approved`` in ``packages/``, ``ai-draft`` in ``drafts/``, ``author``
  elsewhere);
- ``closure``: the statements it rests on, by role: ``definition`` (class
  invariants), ``law`` (laws), ``foundation`` (type-derived facts such as
  ``Angle.unit``, ``Integer.whole``), ``lemma`` (proven theorems it used).
  ``exact`` is true when a certificate recorded exactly which hypotheses it used;
  otherwise the closure is every statement of the class (an upper bound);
- ``steps``: each proof step with a ``role`` (``given``, ``assumption``,
  ``definition``, ``law``, ``key``, ``routine``) and ``proposed_by`` (``z3``,
  ``sympy`` finder, ``engine``, ``kernel``);
- ``lemma_boundaries``: the lemmas whose proofs are separate units.

Untrusted: it reads verdicts and steps, it never makes one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .objects.compile import Classes
from .objects.engine import ObjAnswer
from .runner import FileResult

_STEP_ROLES = (
    ("certificate [kernel", "key", "sympy finder, checked by the kernel"),
    ("uniqueness certificate", "key", "sympy finder, checked by the kernel"),
    ("inherited:", "key", "engine"),
    ("retry with the proven lemmas", "key", "engine"),
    ("lift the model", "routine", "sympy finder"),
    ("re-check [checker]", "routine", "kernel"),
    ("re-solve [z3", "routine", "z3"),
    ("solve [", "routine", "z3"),
    ("enumerate [z3", "routine", "z3"),
)


def _role(kind: str, name: str) -> str:
    if name.startswith(("Angle.", "Integer.")) or "Angle.unit@" in name:
        return "foundation"
    return {"law": "law", "theorem": "lemma", "lemma": "lemma"}.get(kind, "definition")


def _proposed_by(file: str) -> str:
    parts = Path(file).parts
    if "packages" in parts and "drafts" not in parts:
        return "founder-approved"
    return "ai-draft" if "drafts" in parts else "author"


def blueprint(ans: ObjAnswer, classes: Classes, sources: dict[str, str]) -> dict[str, Any]:
    name = ans.title.removeprefix("theorem ")
    cls = classes.defs[name.rpartition(".")[0]]
    span = classes.spans.get(name)
    text = sources.get(span.file, "").splitlines()[span.line - 1].strip() if span else ""
    exact = ans.certified and bool(ans.used_hyps)
    names = list(ans.used_hyps) if exact else [n for n, _ in cls.invariants]
    closure: dict[str, list[str]] = {"definition": [], "law": [], "foundation": [],
                                     "lemma": list(ans.lemmas)}
    for n in names:
        if n in ans.lemmas or n.startswith("given:") or n == "pi_positive":
            continue
        base = n.split("@")[0]
        closure.setdefault(_role(classes.kinds.get(n, classes.kinds.get(base, "")), n), [])
        closure[_role(classes.kinds.get(n, classes.kinds.get(base, "")), n)].append(n)
    steps = [{"role": role, "text": n, "proposed_by": "author" if role != "foundation"
              else "OV"} for role, ns in closure.items() if role != "lemma" for n in ns]
    for s in ans.steps:
        role, who = next(((r, w) for p, r, w in _STEP_ROLES if s.startswith(p)),
                         ("routine", "engine"))
        steps.append({"role": role, "text": s, "proposed_by": who})
    return {
        "theorem": name,
        "statement": {"text": text, "file": span.file if span else "",
                      "line": span.line if span else 0,
                      "proposed_by": _proposed_by(span.file) if span else "author"},
        "verdict": ans.verdict, "trust": sorted(ans.trust_base),
        "closure": {"exact": exact, **closure},
        "steps": steps,
        "lemma_boundaries": list(ans.lemmas),
    }


def blueprints(res: FileResult) -> list[dict[str, Any]]:
    sources = res.env.sources()
    return [blueprint(a, res.env.objects, sources) for a in res.classes
            if a.kind == "theorem"]
