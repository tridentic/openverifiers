"""Load an OVState file (trusted): verify its hash, then read its atoms.

A file is {"sha256": <hex>, "body": {"version": 1, "atoms": [...]}}. The hash is
recomputed from the body's canonical bytes; a mismatch, an unknown version or a
non-canonical atom is refused. The atoms become facts with origin
``import:<name>``: they enter as stated facts of the importing scenario, never
as rules or as anything the kernel derived there.
"""

from __future__ import annotations

import json

from ..raw.canon import atom_from_json
from ..raw.program import Atom, Fact, Span
from ..raw.terms import is_ground
from .hash import VERSION, canonical, digest


class StateError(ValueError):
    """The file is not a valid OVState."""


def load_atoms(text: str) -> tuple[str, tuple[Atom, ...]]:
    d = json.loads(text)
    if not isinstance(d, dict) or set(d) != {"sha256", "body"}:
        raise StateError("an OVState has exactly: sha256, body")
    b = d["body"]
    if not isinstance(b, dict) or b.get("version") != VERSION or set(b) != {"version", "atoms"}:
        raise StateError("unknown OVState version or shape")
    if digest(b) != d["sha256"]:
        raise StateError("the hash does not match the content")
    atoms = tuple(atom_from_json(a) for a in b["atoms"])
    if any(not all(is_ground(t) for t in a.args) for a in atoms) or canonical(b) != canonical(
            {"version": VERSION, "atoms": sorted(b["atoms"], key=lambda r: json.dumps(
                r, sort_keys=True))}):
        raise StateError("atoms must be ground and sorted")
    return d["sha256"], atoms


def facts(name: str, text: str, span: Span | None = None) -> tuple[Fact, ...]:
    _, atoms = load_atoms(text)
    return tuple(Fact(f"state:{name}#{i}", a, f"import:{name}", span)
                 for i, a in enumerate(atoms))
