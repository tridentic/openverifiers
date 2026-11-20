"""Run HSC q11 from hand-written RawOV and print the four verdicts.

    python scripts/q11_raw.py
"""

from __future__ import annotations

from pathlib import Path

from openverifiers.checker import Proven
from openverifiers.engine import ask, find_all, run, without
from openverifiers.raw import Atom, Str, Term, parse, parse_atom

SRC = Path(__file__).resolve().parents[1] / "examples" / "raw" / "q11.rawov"


def main() -> None:
    prog = parse(SRC.read_text())
    r = run(prog)
    names = {a.args[0]: a.args[1].value for a in r.model.atoms()
             if a.pred == "name" and isinstance(a.args[1], Str)}

    def nm(t: Term) -> str:
        return names.get(t) or getattr(t, "name", str(t))

    def assumptions(v: Proven) -> str:
        return "{" + ", ".join(("" if s else "not ") + n for n, s in sorted(v.assumptions)) + "}"

    print(f"trace: {len(r.trace.steps)} steps, checked")
    for s, v in find_all(r, parse_atom("value_acd(A, C, D)")):
        if isinstance(v, Proven):
            print(f"FIND ?A,?C,?D  PROVEN  A={nm(s['A'])} C={nm(s['C'])} D={nm(s['D'])}"
                  f"  assumptions {assumptions(v)}")
    for s, v in find_all(r, parse_atom("q2(P)")):
        if isinstance(v, Proven):
            print(f"FIND ?p        PROVEN  p={nm(s['P'])}  assumptions {assumptions(v)}")
    v3 = ask(r, Atom("q3"))
    print(f"PROVE optically_active(add(C, HCN))  {type(v3).__name__.upper()}"
          f"  ({len(getattr(v3, 'proof', ()))} proof steps)")
    r4 = run(without(prog, {"f_taut"}))
    cands = [nm(s["A"]) for s, v in find_all(r4, parse_atom("cand_acd(A, C, D)"))
             if isinstance(v, Proven)]
    found = [s for s, v in find_all(r4, parse_atom("value_a(A)")) if isinstance(v, Proven)]
    print(f"WHAT IF RETRACT not tautomerizes(D) THEN FIND ?A  "
          f"{'PROVEN' if found else 'UNKNOWN'}  candidates: {', '.join(cands)}")


if __name__ == "__main__":
    main()
