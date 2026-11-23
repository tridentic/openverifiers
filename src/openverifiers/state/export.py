"""``ov state FILE.ov [--scenario NAME] [--out PATH]``: write a scenario's checked
model as an OVState (untrusted glue; the hash and format are state/hash.py).

Only atoms derived unconditionally are written: those whose label holds with no
assumption. An importer reads them as stated facts with origin import:<name>.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ..raw.program import Atom
from ..runner import run_file
from .hash import body, digest


def export(path: Path, scenario: str | None = None) -> dict[str, object]:
    res = run_file(path, files={str(path)})
    names = [scenario] if scenario else sorted(res.runs)
    if len(names) != 1 or names[0] not in res.runs:
        raise SystemExit(f"name one scenario with --scenario (have: {', '.join(sorted(res.runs))})")
    m = res.runs[names[0]].model
    atoms: list[Atom] = [a for a in m.atoms() if frozenset() in m.label(a)]
    b = body(atoms)
    return {"sha256": digest(b), "body": b}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    opts: dict[str, str] = {}
    pos: list[str] = []
    it = iter(args)
    for a in it:
        if a in ("--scenario", "--out"):
            opts[a] = next(it, "")
        else:
            pos.append(a)
    if not pos:
        print("usage: ov state FILE.ov [--scenario NAME] [--out PATH]", file=sys.stderr)
        return 2
    out = export(Path(pos[0]), opts.get("--scenario"))
    text = json.dumps(out, sort_keys=True, indent=1) + "\n"
    if "--out" in opts:
        Path(opts["--out"]).write_text(text)
        print(f"{opts['--out']}: {len(out['body']['atoms'])} atoms, sha256 {out['sha256']}")  # type: ignore[index]
    else:
        print(text, end="")
    return 0
