"""``ov bench``: run the benchmark suites and compare with the hand-written gold.

    ov bench [DIR] [--suite NAME] [--case NAME] [--seeds N] [--out DIR]
             [--strict] [--no-reductions]

Layout: ``DIR/<suite>/<case>/case.ov`` and ``DIR/<suite>/<case>/expected.json``
(DIR defaults to ``benchmarks``). ``expected.json`` is gold, written by hand
and committed before OV first runs on the case (the gold gate enforces both):

    {"suite": "physics", "case": "push_block", "tag": "needs_assumption",
     "why": "...",
     "queries": [{"query": "<the query text>", "verdict": "PROVEN",
                  "values": ["5 kg"], "assumptions": ["frictionless"],
                  "reason": "...", "missing": ["mu", "normal_force"],
                  "why": "..."}],
     "classes": [{"check": "theorem t", "verdict": "PROVEN", "why": "..."}],
     "error": ["E301"]}

Queries are matched in file order and their text is checked, so a gold entry
can never silently attach to a different query. Only the fields gold gives are
compared: ``values`` as a set of rendered values, ``assumptions`` and
``missing`` (predicate names) as sets, ``reason`` exactly. A case whose gold
has ``error`` must fail to load with exactly those codes: OV error codes
(``E301``), ``not_stratifiable`` when the kernel rejects the program, and
``crash:<Exception>`` for anything else (a crash never matches gold).

Each case runs once per seed (z3 seed base ``100 * seed``). Outputs in ``--out``
(default ``bench-out``): ``results.jsonl`` (one row per case and seed),
``summary.csv`` (one row per suite, plus ``all``) and ``summary.md``.

Untrusted tooling: it reads verdicts, it never makes one.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..checker import Inconsistent, Proven, Refuted, Unknown
from ..kernel.strata import NotStratifiable
from ..lang.errors import OVError
from ..lang.units import parse_unit, show_quantity
from ..objects.engine import ObjAnswer, Settings, show
from ..objects.solve import seed_base
from ..runner import Answer, FileResult, _show, run_file

USAGE = ("usage: ov bench [DIR] [--suite NAME] [--case NAME] [--seeds N] [--out DIR] "
         "[--strict] [--no-reductions]")
FIELDS = ("verdict", "values", "assumptions", "reason", "missing", "names")


# ---------------------------------------------------------------- normalising answers


def _rule(a: Answer, res: FileResult) -> dict[str, Any]:
    lw = next(x for x in res.lowered if x.scenario == a.scenario)
    v = a.detail
    out: dict[str, Any] = {"query": a.plan.query.text, "line": a.plan.query.span.line,
                           "verdict": a.verdict, "trust": sorted(a.trust_base)}
    if a.verdict == "PROVEN" and a.bindings:
        out["values"] = sorted(", ".join(_show(s[n], lw) for n in a.plan.vars)
                               for s, _ in a.bindings)
        v = a.bindings[0][1]
    elif a.candidates:
        out["values"] = sorted(_show(t, lw) for c in a.candidates.values() for t in c)
    if isinstance(v, (Proven, Refuted)):
        out["assumptions"] = sorted(n if s else f"not {n}" for n, s in v.assumptions)
    if isinstance(v, Unknown):
        out["reason"] = v.reason
        out["missing"] = sorted({x.pred for alt in v.missing for x in alt})
    if isinstance(v, Inconsistent):
        out["names"] = sorted(v.conflict_set)
    return out


def _obj(a: ObjAnswer) -> dict[str, Any]:
    out: dict[str, Any] = {"query": a.plan.query.text if a.plan else a.title,
                           "line": a.plan.query.span.line if a.plan else 0,
                           "verdict": a.verdict, "trust": sorted(a.trust_base)}
    if a.bindings:
        out["values"] = sorted(", ".join(show(t) for t in b.values()) for b in a.bindings)
    if a.count is not None:
        out["values"] = [str(a.count)]
    if a.reason:
        out["reason"] = a.reason
    if a.names:
        out["names"] = sorted(a.names)
    return out


def outcome(res: FileResult) -> dict[str, Any]:
    """Every query (file order) and class check of one run, as plain data."""
    qs = [_rule(a, res) for a in res.answers] + [_obj(a) for a in res.objects]
    qs.sort(key=lambda q: q["line"])
    classes = [{"check": a.title, "verdict": a.verdict, "reason": a.reason,
                "trust": sorted(a.trust_base)} for a in res.classes]
    return {"queries": qs, "classes": classes}


# ---------------------------------------------------------------- comparing with gold


_QTY = re.compile(r"(-?\d+(?:\.\d+)?(?:/\d+)?)\s+([A-Za-zΩ][A-Za-z0-9Ω/^*·-]*)")


def _qty(m: re.Match[str]) -> str:
    """One quantity in canonical display form: '500 g' -> '0.5 kg', '4 m/s^2' kept."""
    u = parse_unit(m.group(2))
    if u is None:
        return m.group(0)
    return show_quantity(Fraction(m.group(1)) * u[0], u[1])


def value_text(v: str) -> str:
    """A rendered value with every quantity in canonical form and spacing normalised."""
    return " ".join(_QTY.sub(_qty, v).split())


def _norm(x: Any, f: str = "") -> Any:
    if f == "values" and isinstance(x, list):
        return sorted(value_text(str(v)) for v in x)
    return sorted(x) if isinstance(x, list) else x


def compare(gold: dict[str, Any], got: dict[str, Any]) -> list[str]:
    """Mismatches between gold and one run (empty: the case passes)."""
    if "error" in gold or "error" in got:
        if gold.get("error") == got.get("error"):
            return []
        return [f"error: gold {gold.get('error')}, got {got.get('error', 'no error')}"]
    out = []
    gq, oq = gold.get("queries", []), got["queries"]
    if len(gq) != len(oq):
        out.append(f"{len(gq)} gold queries, {len(oq)} in the file")
    for i, (g, o) in enumerate(zip(gq, oq, strict=False)):
        if " ".join(g["query"].split()) != " ".join(o["query"].split()):
            out.append(f"q{i + 1}: gold is for '{g['query']}', the file has '{o['query']}'")
            continue
        for f in FIELDS:
            if f in g and _norm(g[f], f) != _norm(o.get(f), f):
                out.append(f"q{i + 1} {f}: gold {g[f]}, got {o.get(f)}")
    have = {c["check"]: c for c in got["classes"]}
    for g in gold.get("classes", []):
        c = have.get(g["check"])
        if c is None:
            out.append(f"class check '{g['check']}' not run")
        elif c["verdict"] != g["verdict"]:
            out.append(f"{g['check']}: gold {g['verdict']}, got {c['verdict']}")
    return out


# ---------------------------------------------------------------- running


@dataclass
class Case:
    suite: str
    name: str
    path: Path
    gold: dict[str, Any]


def discover(root: Path, suite: str | None = None, case: str | None = None) -> list[Case]:
    out = []
    for exp in sorted(root.glob("*/*/expected.json")):
        d = exp.parent
        if (suite and d.parent.name != suite) or (case and d.name != case):
            continue
        out.append(Case(d.parent.name, d.name, d / "case.ov", json.loads(exp.read_text())))
    return out


def run_case(c: Case, seed: int, st: Settings) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        with seed_base(100 * seed):
            got = outcome(run_file(c.path, files={str(c.path)}, settings=st))
    except OVError as e:
        got = {"error": sorted({d.code for d in e.diagnostics if not d.warning})}
    except NotStratifiable:
        got = {"error": ["not_stratifiable"]}         # the kernel rejects the program
    except Exception as e:                            # a crash is recorded, never gold
        got = {"error": [f"crash:{type(e).__name__}"], "message": str(e)[:300]}
    seconds = time.perf_counter() - start
    bad = compare(c.gold, got)
    return {"suite": c.suite, "case": c.name, "tag": c.gold.get("tag", ""), "seed": seed,
            "seconds": round(seconds, 4), "pass": not bad, "mismatches": bad,
            "outcome": got}


@dataclass
class Stats:
    cases: set[str] = field(default_factory=set)
    passed: set[str] = field(default_factory=set)
    times: list[float] = field(default_factory=list)
    gold_proven_or_not: list[tuple[str, str]] = field(default_factory=list)   # (gold, got)
    varied: set[str] = field(default_factory=set)


def _pct(xs: list[float], q: float) -> float:
    if len(xs) == 1:
        return xs[0]
    return statistics.quantiles(xs, n=100, method="inclusive")[int(q) - 1]


def summarise(rows: list[dict[str, Any]], golds: dict[str, dict[str, Any]]
              ) -> list[dict[str, Any]]:
    by: dict[str, Stats] = {}
    seen: dict[str, str] = {}
    for r in rows:
        key = f"{r['suite']}/{r['case']}"
        for s in (r["suite"], "all"):
            st = by.setdefault(s, Stats())
            st.cases.add(key)
            st.times.append(r["seconds"])
            if r["seed"] == 0:
                if r["pass"]:
                    st.passed.add(key)
                gq = golds[key].get("queries", [])
                oq = r["outcome"].get("queries", [])
                st.gold_proven_or_not += [(g["verdict"], o["verdict"])
                                          for g, o in zip(gq, oq, strict=False)]
                gc = {c["check"]: c["verdict"] for c in golds[key].get("classes", [])}
                st.gold_proven_or_not += [(gc[c["check"]], c["verdict"])
                                          for c in r["outcome"].get("classes", [])
                                          if c["check"] in gc]
        sig = json.dumps(r["outcome"], sort_keys=True)
        if seen.setdefault(key, sig) != sig:
            for s in (r["suite"], "all"):
                by[s].varied.add(key)
    out = []
    for s in sorted(by, key=lambda x: (x == "all", x)):
        st = by[s]
        pairs = st.gold_proven_or_not
        unk = [g for g, o in pairs if o == "UNKNOWN"]
        gold_unk = [o for g, o in pairs if g == "UNKNOWN"]
        out.append({
            "suite": s, "cases": len(st.cases), "passed": len(st.passed),
            "verdicts": len(pairs),
            "false_proven": sum(o == "PROVEN" and g != "PROVEN" for g, o in pairs),
            "false_refuted": sum(o == "REFUTED" and g != "REFUTED" for g, o in pairs),
            "unknown_answers": len(unk),
            "unknown_precision": round(sum(g == "UNKNOWN" for g in unk) / len(unk), 3)
            if unk else "",
            "unknown_recall": round(sum(o == "UNKNOWN" for o in gold_unk) / len(gold_unk), 3)
            if gold_unk else "",
            "p50_s": round(_pct(st.times, 50), 4), "p95_s": round(_pct(st.times, 95), 4),
            "seed_varied_cases": len(st.varied),
        })
    return out


def write(out: Path, rows: list[dict[str, Any]], summary: list[dict[str, Any]],
          seeds: int, flags: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                               for r in rows))
    with (out / "summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    cols = list(summary[0])
    md = [f"# ov bench: {seeds} seed(s){(' ' + flags) if flags else ''}", "",
          "Verdict counts and pass/fail use seed 0; times use every seed.", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in summary]
    fails = [r for r in rows if r["seed"] == 0 and not r["pass"]]
    if fails:
        md += ["", "## Mismatches (seed 0)", ""]
        for r in fails:
            md.append(f"- **{r['suite']}/{r['case']}**: " + "; ".join(r["mismatches"]))
    (out / "summary.md").write_text("\n".join(md) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    opts: dict[str, str] = {}
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--suite", "--case", "--seeds", "--out"):
            if i + 1 >= len(args):
                print(USAGE, file=sys.stderr)
                return 2
            opts[a], i = args[i + 1], i + 2
        elif a in ("--strict", "--no-reductions"):
            opts[a], i = "1", i + 1
        elif a.startswith("-"):
            print(f"ov bench: unknown option {a}\n{USAGE}", file=sys.stderr)
            return 2
        else:
            pos.append(a)
            i += 1
    root = Path(pos[0] if pos else "benchmarks")
    cases = discover(root, opts.get("--suite"), opts.get("--case"))
    if not cases:
        print(f"ov bench: no cases under {root}", file=sys.stderr)
        return 2
    seeds = int(opts.get("--seeds", "1"))
    st = Settings(strict="--strict" in opts, reductions="--no-reductions" not in opts)
    rows = []
    for c in cases:
        for seed in range(seeds):
            r = run_case(c, seed, st)
            rows.append(r)
            if seed == 0:
                print(f"{'ok  ' if r['pass'] else 'FAIL'} {c.suite}/{c.name}  "
                      f"{r['seconds']:.3f}s" + ("" if r["pass"] else
                                                "  " + "; ".join(r["mismatches"])))
    golds = {f"{c.suite}/{c.name}": c.gold for c in cases}
    summary = summarise(rows, golds)
    flags = " ".join(k for k in ("--strict", "--no-reductions") if k in opts)
    write(Path(opts.get("--out", "bench-out")), rows, summary, seeds, flags)
    total = summary[-1]
    print(f"{total['passed']}/{total['cases']} cases pass; false PROVEN "
          f"{total['false_proven']}; p50 {total['p50_s']}s p95 {total['p95_s']}s; "
          f"{total['seed_varied_cases']} case(s) vary across {seeds} seed(s)")
    return 0 if total["passed"] == total["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
