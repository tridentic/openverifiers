"""The canonical bytes and SHA-256 of an OVState body (trusted).

The body is {"version": 1, "atoms": [atom JSON, ...]} with atoms in canonical
JSON (raw/canon.py), sorted by their JSON text; the bytes are that object
serialized with sorted keys and no spaces. Equal sets of atoms give equal bytes,
so the hash names the content.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from ..raw.canon import atom_to_json
from ..raw.program import Atom

VERSION = 1


def body(atoms: Iterable[Atom]) -> dict[str, object]:
    rows = sorted((atom_to_json(a) for a in atoms), key=lambda r: json.dumps(r, sort_keys=True))
    return {"version": VERSION, "atoms": rows}


def canonical(b: dict[str, object]) -> bytes:
    return json.dumps(b, sort_keys=True, separators=(",", ":")).encode()


def digest(b: dict[str, object]) -> str:
    return hashlib.sha256(canonical(b)).hexdigest()
