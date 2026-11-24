# ruff: noqa: E501  (docs tooling: long Graphviz/Typst string templates)
"""Figures, generated tables and lowerings for the Masterbook (docs only).

Loaded by scripts/build_masterbook.py. Every function here reads real data:
source files, real runs of the OV pipeline, OVTrace files written during the
build, ``ov audit``, ``git log`` and reproduce.sh's outputs. Diagrams whose
subject is a design rather than data are marked ``conceptual`` in their caption.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

B: Any = None          # the build module
N: Any = None          # Numbers
ARGS: Any = None

IMPL, PART, PLAN = "#d8efdf", "#fbe7c6", "#e2dcf7"
TRUST = "#f6c9c4"


def register(build: Any, nums: Any, args: Any) -> None:
    global B, N, ARGS
    B, N, ARGS = build, nums, args
    fig, gen = build.figure, build.GENS
    for name, (fn, caption, kind, width, planned) in FIGDEFS.items():
        fig(name, caption, kind, width, planned)(fn)
    gen.update(GENDEFS)
    prepare_state_files()
    audit_totals()
    build.LOWERINGS.update(LOWERDEFS)


ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "src" / "openverifiers"


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def wrap(s: str, n: int = 38) -> str:
    out, line = [], ""
    for w in s.split(" "):
        if len(line) + len(w) > n and line:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    out.append(line)
    return "\\n".join(esc(x) for x in out)


def G(body: str, rankdir: str = "TB", extra: str = "") -> str:
    return (f"digraph G {{\n  graph [rankdir={rankdir}, fontname=\"Helvetica\", fontsize=10, "
            f"nodesep=0.25, ranksep=0.35, bgcolor=\"white\", size=\"6.5,8.4\" {extra}];\n"
            "  node [fontname=\"Helvetica\", fontsize=9, shape=box, style=\"rounded,filled\", "
            "fillcolor=\"#f4f4f4\", color=\"#666666\", margin=\"0.08,0.04\"];\n"
            "  edge [fontname=\"Helvetica\", fontsize=8, color=\"#555555\", arrowsize=0.6];\n"
            f"{body}\n}}\n")


# ============================================================================ helpers: OV


def run_file(path: str | Path, **kw: Any) -> Any:
    from openverifiers.runner import run_file as rf
    p = ROOT / path if not Path(path).is_absolute() else Path(path)
    return rf(p, files={str(p)}, **kw)


def write_trace(name: str, res: Any, scenario: str) -> Path:
    from openverifiers.raw.trace import dumps
    B.TRACES.mkdir(parents=True, exist_ok=True)
    out = B.TRACES / f"{name}.jsonl"
    out.write_text(dumps(res.runs[scenario].trace))
    return out


def atom_text(a: Any, names: dict[Any, str] | None = None) -> str:
    from openverifiers.rawtext import dump_atom
    return dump_atom(a)


def proof_dag(trace_path: Path, proof_ids: tuple[int, ...], title: str,
              highlight: int | None = None) -> str:
    """A proof DAG read back from an OVTrace JSON-lines file."""
    from openverifiers.raw.canon import atom_from_json
    rows = [json.loads(x) for x in trace_path.read_text().splitlines()]
    steps = {r["id"]: r for r in rows if r.get("kind") != "header"}
    ids = set(proof_ids)
    lines = []
    for i in sorted(ids):
        s = steps[i]
        a = atom_text(atom_from_json(s["conclusion"]))
        lab = s["label"]
        labt = "{" + ", ".join("{" + ",".join(e) + "}" for e in lab) + "}"
        span = s.get("source_span")
        where = f"{Path(span[0]).name}:{span[1]}" if span else ""
        fill = "#e8f1fb" if not s["premises"] and not s.get("naf") else "#f4f4f4"
        if i == highlight or i == max(ids):
            fill = "#d8efdf"
        lbl = f"#{i} {wrap(s['rule_id'], 40)}\\n{wrap(a, 44)}\\nlabel {esc(labt)}  {esc(where)}"
        lines.append(f'  s{i} [label="{lbl}", fillcolor="{fill}"];')
        for p in s["premises"]:
            if p in ids:
                lines.append(f"  s{p} -> s{i};")
        for k, n in enumerate(s.get("naf", [])):
            if n.get("step") in ids:
                lines.append(f'  s{n["step"]} -> s{i} [style=dashed, label="not"];')
            elif n.get("step") is None:
                na = atom_text(atom_from_json(n["atom"]))
                lines.append(f'  n{i}_{k} [label="not {esc(na)}\\nabsent from the complete model", '
                             f'style="dashed,rounded", fillcolor="white"];')
                lines.append(f'  n{i}_{k} -> s{i} [style=dashed];')
    lines.append(f'  labelloc="t"; label="{esc(title)}";')
    return G("\n".join(lines))


# ============================================================================ figures: architecture

LAYERS = [
    ("L9", "Applications", "PARTIAL", "exams (JEE 2025), agent guardrails (agent.workflow); NDC, LifeOS, enterprise: planned"),
    ("L8", "Interfaces", "PARTIAL", "ov CLI, ov gate, MCP tool-call gate (mcp_gate.py), Python API (runner, engine); no SDK doc, LSP, REST"),
    ("L7", "Modes", "PARTIAL", "CHECK, FIND, PROVE UNIQUE, COUNT, WHY, WHY NOT, WHAT IF, COUNTEREXAMPLE; PROPAGATE..EXPLAIN planned"),
    ("L6", "Knowledge", "PARTIAL", "packages/ (15 .ov), drafts/, OVState export+import; mappings, adapters, registry planned"),
    ("L5", "Languages", "PARTIAL", "OV (lang/grammar.lark), OKQL subset inside .ov files; OV-Prose planned (v3)"),
    ("L4", "Lowering", "IMPLEMENTED", "lang/check.py, lang/units.py, lower/lower.py, objects/compile.py"),
    ("L3", "Solvers & procedures", "PARTIAL", "z3, sympy finder, small-scope (objects/); procedures, optimizers planned"),
    ("L2", "Evaluator", "PARTIAL", "kernel/evaluate.py semi-naive, labels, strata, budgets; semirings, incremental planned"),
    ("L1", "Kernel checker (trusted)", "IMPLEMENTED", "checker/, raw/ data model, raw/certificate.py, state/hash+load"),
    ("L0", "Exact arithmetic (trusted)", "IMPLEMENTED", "Fraction, raw/surd.py, raw/interval.py, raw/qpi.py, raw/formula.py"),
]


def fig_layers() -> str:
    col = {"IMPLEMENTED": IMPL, "PARTIAL": PART, "PLANNED": PLAN}
    rows = []
    for lid, name, st, what in LAYERS:
        border = ' color="#c0392b" penwidth=2' if lid in ("L0", "L1") else ""
        rows.append(f'  {lid} [label="{lid}  {esc(name)}   [{st}]\\n{wrap(what, 90)}", '
                    f'fillcolor="{col[st]}", width=6.0{border}];')
    edges = " -> ".join(lid for lid, *_ in LAYERS)
    return G("\n".join(rows) + f"\n  {edges} [style=invis];\n"
             '  legend [shape=plaintext, style="", label="red border: trusted (TCB)   '
             'green: IMPLEMENTED   orange: PARTIAL   purple: PLANNED"];\n  L0 -> legend [style=invis];')


def fig_pipeline() -> str:
    return G("""
  src [label="OV source\\n(.ov file + imported packages)", fillcolor="#e8f1fb"];
  parse [label="parse\\nlang/parser.py + grammar.lark (LALR)"];
  check [label="name, type and unit check\\nlang/check.py, lang/units.py"];
  lower [label="lower\\nlower/lower.py"];
  raw [label="RawOV Program\\nfacts, rules, domains, worlds\\n(raw/program.py)", fillcolor="#e8f1fb"];
  canon [label="canonical JSON\\nraw/canon.py", fillcolor="#f6c9c4"];
  eval [label="semi-naive evaluator\\nkernel/evaluate.py (untrusted)"];
  trace [label="OVTrace JSON lines\\nraw/trace.py", fillcolor="#e8f1fb"];
  checker [label="trace checker\\nchecker/check.py (trusted)", fillcolor="#f6c9c4"];
  model [label="CheckedModel", fillcolor="#e8f1fb"];
  verdict [label="verdicts\\nchecker/verdict.py (trusted)", fillcolor="#f6c9c4"];
  state [label="OVState\\nstate/export.py -> state/hash.py\\n(SHA-256)", fillcolor="#e8f1fb"];
  load [label="state/load.py (trusted)\\nimport state ... as n", fillcolor="#f6c9c4"];
  compile [label="object layer\\nobjects/compile.py"];
  engine [label="objects/engine.py\\nz3, sympy, small-scope (untrusted)"];
  records [label="JSON records\\n(models, certificates)", fillcolor="#e8f1fb"];
  ocheck [label="checker/objects.py\\nraw/formula.py, raw/certificate.py\\n(trusted)", fillcolor="#f6c9c4"];
  ans [label="answers: PROVEN / REFUTED /\\nUNKNOWN / INCONSISTENT + trust_base", fillcolor="#d8efdf"];
  src -> parse -> check -> lower -> raw -> canon -> eval -> trace -> checker;
  canon -> checker [label="program"];
  checker -> model -> verdict -> ans;
  model -> state [label="ov state"]; state -> load [label="later file"]; load -> raw [style=dashed, label="facts import:n"];
  check -> compile -> engine -> records -> ocheck -> ans;
""")


def tcb_files() -> tuple[list[str], list[str], list[str]]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("tcb", ROOT / "scripts" / "tcb_size.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    main = [str(p.relative_to(m.ROOT)) for p in m.trusted_files()]
    return main, list(m.UNITS), list(m.EXACT)


def fig_trust() -> str:
    main, units, exact = tcb_files()
    inside = []
    for f in main:
        inside.append(f'    "{f}" [fillcolor="{TRUST}"];')
    for f in units:
        inside.append(f'    "{f}" [fillcolor="#f2a29a"];')
    for f in exact:
        inside.append(f'    "{f}" [fillcolor="#f9d9d5"];')
    return G("""
  subgraph cluster_t {{ label="trusted computing base (scripts/tcb_size.py): only this decides"; style="rounded,filled"; fillcolor="#fff3f1"; color="#c0392b";
{}
  }}
  subgraph cluster_u {{ label="untrusted proposers: may only propose (MP-INV)"; style="rounded"; color="#888888";
    "lang/ (parser, checker)"; "lower/lower.py"; "kernel/evaluate.py"; "objects/ (compile, engine, z3, sympy)"; "agents / LLM authors"; "bench/, audit.py, gate.py, mcp_gate.py";
  }}
  "kernel/evaluate.py" -> "checker/check.py" [label="OVTrace JSON"];
  "objects/ (compile, engine, z3, sympy)" -> "checker/objects.py" [label="records JSON"];
  "lower/lower.py" -> "raw/canon.py" [label="program JSON"];
  "agents / LLM authors" -> "lang/ (parser, checker)" [label=".ov text"];
""".format("\n".join(inside)), rankdir="LR")


# ---------------------------------------------------------------------------- imports

SKIP = ("legacy", "m1", "packages")


def module_graph() -> tuple[dict[str, set[str]], dict[str, int]]:
    mods: dict[str, Path] = {}
    for p in sorted(PKG.rglob("*.py")):
        r = p.relative_to(PKG)
        if r.parts[0] in SKIP:
            continue
        name = ".".join(r.with_suffix("").parts)
        if name.endswith("__init__"):
            name = name[: -len(".__init__")] or "openverifiers"
        mods[name] = p
    edges: dict[str, set[str]] = defaultdict(set)
    sizes = {}
    for name, p in mods.items():
        sizes[name] = len(p.read_text().splitlines())
        pkg = name.split(".") if p.name == "__init__.py" else name.split(".")[:-1]
        for node in ast.walk(ast.parse(p.read_text())):
            targets = []
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = pkg[: len(pkg) - node.level + 1] if node.level > 1 else pkg
                    mod = ".".join([*base, *(node.module.split(".") if node.module else [])])
                    targets.append(mod)
                    for a in node.names:
                        targets.append(f"{mod}.{a.name}" if mod else a.name)
                elif node.module and node.module.startswith("openverifiers"):
                    targets.append(node.module.removeprefix("openverifiers").lstrip("."))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("openverifiers."):
                        targets.append(a.name.removeprefix("openverifiers."))
            for t in targets:
                t = t.strip(".")
                if t in mods and t != name:
                    edges[name].add(t)
                    break
    return edges, sizes


def fig_imports() -> str:
    edges, sizes = module_graph()
    main, units, exact = tcb_files()
    trusted = {f.replace("/", ".").removesuffix(".py").removesuffix(".__init__")
               for f in [*main, *units, *exact]}
    groups: dict[str, list[str]] = defaultdict(list)
    for m in sizes:
        groups[m.split(".")[0] if "." in m else "(top)"].append(m)
    out = []
    for g, ms in sorted(groups.items()):
        out.append(f'  subgraph cluster_{re.sub(r"[^a-z]", "_", g)} {{ label="{g}"; style="rounded"; color="#999999";')
        for m in sorted(ms):
            fill = TRUST if m in trusted else "#f4f4f4"
            out.append(f'    "{m}" [label="{m}\\n{sizes[m]} lines", fillcolor="{fill}"];')
        out.append("  }")
    for a, bs in sorted(edges.items()):
        for b in sorted(bs):
            out.append(f'  "{a}" -> "{b}";')
    return G("\n".join(out), rankdir="LR", extra=', ranksep=0.9, nodesep=0.08, concentrate=true')


def fig_imports_pkg() -> str:
    edges, sizes = module_graph()
    _main, _units, _exact = tcb_files()
    tot: dict[str, int] = defaultdict(int)
    for m, n in sizes.items():
        tot[m.split(".")[0] if "." in m else m] += n
    pe: dict[tuple[str, str], int] = defaultdict(int)
    for a, bs in edges.items():
        for b in bs:
            ga, gb = (a.split(".")[0] if "." in a else a), (b.split(".")[0] if "." in b else b)
            if ga != gb:
                pe[(ga, gb)] += 1
    trusted_pkgs = {"raw", "checker"}
    out = []
    for g, n in sorted(tot.items()):
        fill = TRUST if g in trusted_pkgs else ("#fbe2de" if g == "state" else "#f4f4f4")
        out.append(f'  "{g}" [label="{g}\\n{n} lines", fillcolor="{fill}"];')
    for (a, b), k in sorted(pe.items()):
        out.append(f'  "{a}" -> "{b}" [label="{k}"];')
    return G("\n".join(out), rankdir="BT")


# ---------------------------------------------------------------------------- packages


def ov_packages() -> list[dict[str, Any]]:
    out = []
    for base, approved in ((PKG / "packages", True), (ROOT / "drafts" / "packages", False),
                           (ROOT / "drafts" / "policies", False)):
        for p in sorted(base.rglob("*.ov")):
            t = p.read_text()
            m = re.search(r"^\s*package\s+([\w.]+)\s*(@\S+)?", t, re.M)
            if not m:
                continue
            imps = re.findall(r"^\s*import\s+([\w.]+)\s*$", t, re.M)
            out.append({"name": m.group(1), "version": m.group(2) or "", "file": B.rel(p),
                        "approved": approved, "imports": imps,
                        "lines": len(t.splitlines()),
                        "classes": len(re.findall(r"^\s*fact type\s", t, re.M)),
                        "theorems": len(re.findall(r"^\s*(theorem|lemma)\s", t, re.M)),
                        "laws": len(re.findall(r"^\s*law\s", t, re.M)),
                        "axioms": len(re.findall(r"^\s*(axiom|definition)\s", t, re.M))})
    return out


def fig_tower() -> str:
    pk = ov_packages()
    out = []
    for p in pk:
        fill = IMPL if p["approved"] else PLAN
        out.append(f'  "{p["name"]}" [label="{p["name"]} {esc(p["version"])}\\n'
                   f'{p["classes"]} classes, {p["theorems"]} theorems/lemmas\\n'
                   f'{"packages/" if p["approved"] else "drafts/ (unapproved)"}", fillcolor="{fill}"];')
        for i in p["imports"]:
            out.append(f'  "{p["name"]}" -> "{i}";')
    return G("\n".join(out), rankdir="BT")


def audit_json(pkg: str, *dag: str) -> dict[str, Any]:
    extra = " ".join(f"--dag {d}" for d in dag)
    r = B.sh(f"ov audit {pkg} --json {extra}")
    return json.loads(r.stdout)


def prepare_state_files() -> None:
    """Write the OVState demo files into build/work/ from tests/v1/test_state.py.

    They are not committed: a package file outside drafts/ would fall under the
    meaning gate (D-025), and the book must not add meaning lines.
    """
    tree = ast.parse((ROOT / "tests/v1/test_state.py").read_text())
    consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and isinstance(n.value, ast.Constant)}
    w = B.WORK
    w.mkdir(parents=True, exist_ok=True)
    (w / "fam.ov").write_text(consts["FAM"])
    (w / "use.ov").write_text(consts["USE"])
    (w / "use_tampered.ov").write_text(consts["USE"].replace("fam.json", "fam_tampered.json"))
    from openverifiers.state.export import export
    out = export(w / "fam.ov")
    text = json.dumps(out, sort_keys=True, indent=1) + "\n"
    (w / "fam.json").write_text(text)
    (w / "fam_tampered.json").write_text(text.replace('"bob"', '"zed"'))


AUDITS: dict[str, dict[str, Any]] = {}


def audit_totals() -> None:
    """Run ov audit on every approved package once; derive the {kernel} share."""
    k = total = proven = 0
    for p in ov_packages():
        if not p["approved"]:
            continue
        d = audit_json(p["name"])
        AUDITS[p["name"]] = d
        for t in d["theorems"]:
            total += 1
            proven += t["status"] == "PROVEN"
            k += t["status"] == "PROVEN" and t.get("trust") == ["kernel"]
    N.v["audit.kernel"], N.v["audit.theorems"], N.v["audit.proven"] = str(k), str(total), str(proven)
    N.v["audit.kernel_pct"] = f"{round(100 * k / total)}%" if total else "?"
    N.v["audit.packages"] = str(len(AUDITS))


def fig_audit_dag() -> str:
    d = audit_json("physics.mechanics", "ConstantAcceleration.suvat_timeless")
    out = []

    def walk(n: dict[str, Any]) -> str:
        nid = n["name"]
        fill = {"theorem": IMPL, "definition": "#e8f1fb", "law": PART}.get(n["kind"], "#f4f4f4")
        st = f'\\n{n.get("status", "")} {"{" + ",".join(n.get("trust", [])) + "}" if n.get("trust") else ""}'
        out.append(f'  "{nid}" [label="{esc(nid)}\\n({n["kind"]}){st}", fillcolor="{fill}"];')
        for f in n.get("foundations", []):
            out.append(f'  "{f}" [shape=ellipse, fillcolor="#eeeeee"];  "{nid}" -> "{f}" [style=dotted];')
        for u in n.get("uses", []):
            out.append(f'  "{nid}" -> "{walk(u)}";')
        return nid

    walk(d["dags"]["ConstantAcceleration.suvat_timeless"])
    return G("\n".join(dict.fromkeys(out)))


# ============================================================================ grammar


def lark_rules(text: str) -> list[tuple[str, bool, str]]:
    """(name, inlined, expansion) for every rule of a .lark file (terminals included)."""
    text = re.sub(r"//[^\n]*", "", text)
    out: list[tuple[str, bool, str]] = []
    cur: list[str] | None = None
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("%"):
            continue
        m = re.match(r"^([?!]?)([A-Za-z_][A-Za-z0-9_]*)(\.-?\d+)?\s*:\s*(.*)$", line)
        if m and not line[0].isspace():
            cur = [m.group(2), m.group(1) == "?", m.group(4)]
            out.append(cur)  # type: ignore[arg-type]
        elif cur is not None:
            cur[2] = cur[2] + " " + line.strip()
    return [(a, b, c) for a, b, c in out]  # type: ignore[misc]


TOK = re.compile(r'\s*("(?:[^"\\]|\\.)*"i?|/(?:[^/\\]|\\.)+/[imslux]*|->|[A-Za-z_][A-Za-z0-9_]*|[()\[\]|*+?~]|\d+)')


def parse_expansion(s: str) -> Any:
    toks = [t for t in TOK.findall(s)]
    pos = 0

    def peek() -> str | None:
        return toks[pos] if pos < len(toks) else None

    def alts() -> Any:
        nonlocal pos
        out = [seq()]
        while peek() == "|":
            pos += 1
            out.append(seq())
        return ("alt", out) if len(out) > 1 else out[0]

    def seq() -> Any:
        nonlocal pos
        items = []
        while peek() not in (None, "|", ")", "]"):
            if peek() == "->":
                pos += 2            # alias
                continue
            items.append(post())
        return ("seq", items)

    def post() -> Any:
        nonlocal pos
        a = atom()
        while peek() in ("*", "+", "?"):
            op = toks[pos]
            pos += 1
            a = (op, a)
        return a

    def atom() -> Any:
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            x = alts()
            pos += 1
            return x
        if t == "[":
            x = alts()
            pos += 1
            return ("?", x)
        return ("t", t)

    return alts()


def ebnf(x: Any, top: bool = True) -> str:
    k = x[0]
    if k == "t":
        return x[1]
    if k == "seq":
        return " ".join(ebnf(i, False) for i in x[1]) or "(* empty *)"
    if k == "alt":
        s = " | ".join(ebnf(i, False) for i in x[1])
        return s if top else f"( {s} )"
    if k == "?":
        return f"[ {ebnf(x[1])} ]"
    if k == "*":
        return f"{{ {ebnf(x[1])} }}"
    if k == "+":
        return f"{ebnf(x[1], False)} {{ {ebnf(x[1], False)} }}"
    return str(x)


def railroad(name: str, x: Any) -> str:
    """A railroad diagram of one rule, as a left-to-right Graphviz graph."""
    nodes: list[str] = []
    edges: list[str] = []
    cnt = [0]

    def pt() -> str:
        cnt[0] += 1
        n = f"p{cnt[0]}"
        nodes.append(f'  {n} [shape=point, width=0.03, style="", label=""];')
        return n

    def item(label: str) -> str:
        cnt[0] += 1
        n = f"n{cnt[0]}"
        if label.startswith('"'):
            nodes.append(f'  {n} [label="{esc(label.strip(chr(34)))}", shape=box, style="rounded,filled", fillcolor="#fff2cc"];')
        elif label.startswith("/"):
            nodes.append(f'  {n} [label="regex", shape=box, style="rounded,filled", fillcolor="#eeeeee"];')
        elif label.isupper():
            nodes.append(f'  {n} [label="{label}", shape=box, style="filled", fillcolor="#e8f1fb"];')
        else:
            nodes.append(f'  {n} [label="{label}", shape=box, style="filled", fillcolor="#f4f4f4"];')
        return n

    def build(x: Any, a: str, b: str) -> None:
        k = x[0]
        if k == "t":
            n = item(x[1])
            edges.append(f"  {a} -> {n}; {n} -> {b};")
        elif k == "seq":
            if not x[1]:
                edges.append(f"  {a} -> {b};")
                return
            cur = a
            for i, it in enumerate(x[1]):
                nxt = b if i == len(x[1]) - 1 else pt()
                build(it, cur, nxt)
                cur = nxt
        elif k == "alt":
            for it in x[1]:
                build(it, a, b)
        elif k == "?":
            build(x[1], a, b)
            edges.append(f'  {a} -> {b} [style=dashed, color="#999999"];')
        elif k == "*":
            m1 = pt()
            edges.append(f"  {a} -> {m1};")
            m2 = pt()
            build(x[1], m1, m2)
            edges.append(f'  {m2} -> {m1} [constraint=false, color="#999999"];')
            edges.append(f"  {m2} -> {b};")
            edges.append(f'  {m1} -> {b} [style=dashed, color="#999999"];')
        elif k == "+":
            m1, m2 = pt(), pt()
            edges.append(f"  {a} -> {m1};")
            build(x[1], m1, m2)
            edges.append(f'  {m2} -> {m1} [constraint=false, color="#999999"];')
            edges.append(f"  {m2} -> {b};")

    nodes.append(f'  start [label="{name}", shape=plaintext, style="", fontname="Helvetica-Bold"];')
    nodes.append('  end [shape=doublecircle, width=0.08, label="", style=""];')
    build(x, "start", "end")
    return ("digraph R {\n  graph [rankdir=LR, nodesep=0.12, ranksep=0.18, bgcolor=white, size=\"6.4,4\"];\n"
            '  node [fontname="Helvetica", fontsize=9, height=0.22, margin="0.05,0.02"];\n'
            "  edge [arrowsize=0.4, color=\"#444444\"];\n" + "\n".join(nodes) + "\n"
            + "\n".join(edges) + "\n}\n")


GRAMMAR = PKG / "lang" / "grammar.lark"
RAIL_GROUPS = {
    "rail_decls": ("Declarations (packages, imports, types, predicates, axioms)",
                   ["package", "import_pkg", "import_state", "type_decl", "field", "predicate",
                    "output", "function", "entity", "axiom", "axiom_kind"]),
    "rail_brief": ("The brief's core constructs (transformation, controller, generator, target)",
                   ["transformation", "controller", "ctrl", "gen_decl", "gen_use", "target", "must",
                    "prefer"]),
    "rail_scenario": ("Scenarios, statements and tests",
                      ["scenario", "stmt", "fact", "assume", "meta", "tolerance", "test"]),
    "rail_objects": ("The object layer (fact types and class bodies)",
                     ["fact_type", "member", "tyexpr", "fbody", "fseq", "fquant", "fsimple",
                      "fchain"]),
    "rail_okql": ("OKQL queries and expectations",
                  ["query", "okql", "qvars", "qvar_t", "change", "expect"]),
    "rail_expr": ("Formulas and expressions",
                  ["conj", "fact_lit", "lit", "cmp", "sum", "product", "unary", "power", "postfix",
                   "pfield", "atom", "args"]),
}


def rail_group(gid: str) -> str:
    _, names = RAIL_GROUPS[gid]
    rules = {n: e for n, _, e in lark_rules(GRAMMAR.read_text())}
    cells = []
    for n in names:
        if n not in rules:
            B.fail(f"railroad: rule {n} not in grammar.lark")
            continue
        svg = B.dot_to_svg(f"{gid}_{n}", railroad(n, parse_expansion(rules[n])))
        cells.append(f'image("/build/fig/{svg.name}", width: auto, height: auto)')
    return ("block(width: 100%, stack(spacing: 4pt, " +
            ", ".join(f"align(left, {c})" for c in cells) + "))")


# ============================================================================ figures: semantics


LABELS_RAW = "docs/masterbook/examples/labels.rawov"


def labels_run() -> Any:
    from openverifiers.engine import run
    from openverifiers.rawtext import parse
    return run(parse((ROOT / LABELS_RAW).read_text()))


def fig_labels() -> str:
    r = labels_run()
    from openverifiers.raw.trace import dumps
    B.TRACES.mkdir(parents=True, exist_ok=True)
    (B.TRACES / "labels.jsonl").write_text(dumps(r.trace))
    rows = [json.loads(x) for x in (B.TRACES / "labels.jsonl").read_text().splitlines()]
    steps = [x for x in rows if x.get("kind") != "header"]
    from openverifiers.raw.canon import atom_from_json
    out = []
    for s in steps:
        a = atom_text(atom_from_json(s["conclusion"]))
        lab = "{" + ", ".join("{" + ",".join(e) + "}" for e in s["label"]) + "}"
        fill = "#e8f1fb" if not s["premises"] else "#f4f4f4"
        out.append(f'  s{s["id"]} [label="#{s["id"]} {esc(s["rule_id"])}\\n{esc(a)}\\nlabel {esc(lab)}", fillcolor="{fill}"];')
        for p in s["premises"]:
            out.append(f"  s{p} -> s{s['id']};")
        for n in s.get("naf", []):
            if n.get("step") is not None:
                out.append(f'  s{n["step"]} -> s{s["id"]} [style=dashed, color="#c0392b", label="not"];')
        if s.get("prev") is not None:
            out.append(f'  s{s["prev"]} -> s{s["id"]} [style=dotted, label="prev"];')
    return G("\n".join(out))


def fig_strata() -> str:
    from openverifiers.kernel.strata import stratify
    from openverifiers.raw.program import Naf, Pos, effective_body
    from openverifiers.rawtext import parse
    prog = parse((ROOT / LABELS_RAW).read_text())
    st = stratify(prog)
    by: dict[int, list[str]] = defaultdict(list)
    for k, s in st.items():
        by[s].append(k)
    out = []
    for s, ks in sorted(by.items()):
        out.append(f'  subgraph cluster_s{s} {{ label="stratum {s}"; style="rounded"; color="#888888";')
        for k in sorted(ks):
            out.append(f'    "{k}";')
        out.append("  }")
    for r in prog.rules:
        for lit in effective_body(r, prog):
            if isinstance(lit, Pos):
                out.append(f'  "{lit.atom.key}" -> "{r.head.key}" [label="{r.id}"];')
            elif isinstance(lit, Naf):
                out.append(f'  "{lit.atom.key}" -> "{r.head.key}" [label="not ({r.id})", style=dashed, color="#c0392b"];')
    return G("\n".join(out), rankdir="BT")


def fig_verdicts() -> str:
    return G("""
  q [label="ground query q, context C\\n(default C = all declared assumptions)", fillcolor="#e8f1fb"];
  n1 [label="C satisfies some nogood n in N?", shape=diamond, style="filled", fillcolor="#ffffff"];
  inc [label="INCONSISTENT(conflict_set)", fillcolor="#f6c9c4"];
  n2 [label="C satisfies some E in label(q)?", shape=diamond, style="filled", fillcolor="#ffffff"];
  pro [label="PROVEN(proof, E)", fillcolor="#d8efdf"];
  n3 [label="C satisfies some E in label(neg q)?", shape=diamond, style="filled", fillcolor="#ffffff"];
  ref [label="REFUTED(proof, E)", fillcolor="#fbe7c6"];
  n4 [label="q closed-world and its stratum complete?", shape=diamond, style="filled", fillcolor="#ffffff"];
  refc [label="REFUTED (closed_world)", fillcolor="#fbe7c6"];
  unk [label="UNKNOWN(missing, reason)\\nbudget | missing_facts | open_world", fillcolor="#eeeeee"];
  q -> n1; n1 -> inc [label="yes"]; n1 -> n2 [label="no"];
  n2 -> pro [label="yes"]; n2 -> n3 [label="no"];
  n3 -> ref [label="yes"]; n3 -> n4 [label="no"];
  n4 -> refc [label="yes"]; n4 -> unk [label="no"];
""")


def fig_cert_flow() -> str:
    return G("""
  goal [label="claim: theorem or uniqueness\\n(goal = 0 under hypotheses h_i)", fillcolor="#e8f1fb"];
  z3 [label="z3 (untrusted)\\nsays unsat: gives the verdict a direction"];
  finder [label="certificate finder (untrusted)\\nobjects/certify.py: sympy Groebner,\\nGauss pre-pass, LDL, pseudo-division"];
  cert [label="Certificate (JSON record)\\nfactors, coeffs c_i, squares, weighted squares,\\npositive sums, induction, witnesses", fillcolor="#e8f1fb"];
  checker [label="checker/objects.py -> raw/certificate.py\\n(trusted): rebuild hypotheses from the\\ncompiled class, never from the record", fillcolor="#f6c9c4"];
  nf [label="exact normal form\\nm*(lhs - rhs) - sum c_i h_i - sum w_j q_j^2 == 0 ?\\n(Q, sqrt k, pi, exp/ln atoms)", fillcolor="#f6c9c4"];
  yes [label="PROVEN trust {kernel}", fillcolor="#d8efdf"];
  no [label="record rejected:\\nverdict falls back (z3_unsat or UNKNOWN)", fillcolor="#eeeeee"];
  goal -> z3 -> finder -> cert -> checker -> nf; nf -> yes [label="0"]; nf -> no [label="not 0 / side condition fails"];
""")


def fig_qpi() -> str:
    from openverifiers.raw import interval as I
    from openverifiers.raw.qpi import QPi
    pi = I.pi()
    x = QPi.make((Fraction(22, 7), Fraction(-1)), (Fraction(1),))
    iv = x.iv()
    s = x.sign()

    def f(q: Fraction, n: int = 22) -> str:
        return f"{float(q):.{n}g}" if abs(q) > 1e-30 else str(q)
    w = pi.hi - pi.lo
    return G(f"""
  e [label="x = 22/7 - pi  in Q(pi):  numerator poly (22/7, -1), denominator (1)", fillcolor="#e8f1fb"];
  p [label="pi enclosure (raw/interval.py, Machin series with remainder bounds)\\n[{f(pi.lo)},\\n {f(pi.hi)}]\\nwidth {float(w):.2e}", fillcolor="#f6c9c4"];
  h [label="Horner over the interval: p(pi) * q(pi)\\n[{f(iv.lo)}, {f(iv.hi)}]", fillcolor="#f6c9c4"];
  d [label="0 outside the interval?", shape=diamond, style=filled, fillcolor=white];
  y [label="sign = {s:+d}  (computed in this build by raw/qpi.py QPi.sign)", fillcolor="#d8efdf"];
  n [label="QPiError: the enclosure of pi does not decide the sign\\n(no verdict; never a guess)", fillcolor="#eeeeee"];
  e -> h; p -> h; h -> d; d -> y [label="yes"]; d -> n [label="no"];
""")


def fig_exp_rules() -> str:
    return G("""
  subgraph cluster_r { label="indeterminates and rewrite rules of the trusted normal form (raw/certificate.py)"; style=rounded;
  e [label="exp(u)  ->  atom E_u,   E_u > 0"];
  de [label="d/dt E_u  =  u' * E_u   (chain rule)"];
  l [label="ln(u)  ->  atom L_u   needs witness u = c*h1*..*hk*exp(..) > 0"];
  dl [label="d/dt L_u  =  u' * inv(u)"];
  i [label="a / u  ->  a * inv(u)   (u non-constant: witness u > 0)"];
  di [label="d/dt inv(u)  =  - u' * inv(u)^2"];
  c [label="u * inv(u) = 1   only with a checked witness"];
  s [label="sqrt k: indeterminate with (sqrt k)^2 = k"];
  pi [label="pi: indeterminate, sign by enclosure (Q(pi))"];
  trig [label="sin/cos of a variable (S_u, C_u, S^2 + C^2 = 1): D-033, on v1 after bd2ed44", fillcolor="#e2dcf7"];
  }
  e -> de; l -> dl; i -> di; dl -> c; di -> c;
""")


def fig_find_seq() -> str:
    res = run_file("examples/geometry/square.ov")
    a = res.objects[0]
    out = []
    prev = None
    for i, s in enumerate(a.steps):
        fill = "#f6c9c4" if "[checker]" in s else ("#fbe7c6" if "z3" in s else "#f4f4f4")
        out.append(f'  s{i} [label="{wrap(s, 60)}", fillcolor="{fill}"];')
        if prev is not None:
            out.append(f"  s{prev} -> s{i};")
        prev = i
    b = ", ".join(f"?{k} = {v}" for k, v in ((k, B_show(t)) for k, t in a.bindings[0].items()))
    out.append(f'  v [label="{a.verdict}  {esc(b)}  trust {{{", ".join(sorted(a.trust_base))}}}", fillcolor="#d8efdf"];')
    out.append(f"  s{prev} -> v;")
    out.append('  labelloc="t"; label="examples/geometry/square.ov:26, steps read from the engine\'s answer";')
    return G("\n".join(out))


def B_show(t: Any) -> str:
    from openverifiers.objects.engine import show
    return show(t)


def fig_state_life() -> str:
    return G("""
  a [label="fam.ov scenario family\\n(facts, rules, assume maybe)", fillcolor="#e8f1fb"];
  b [label="ov run: evaluate, check trace\\n-> CheckedModel"];
  c [label="state/export.py: keep atoms whose label\\ncontains the empty environment (no assumption)"];
  d [label="state/hash.py: sort canonical atom JSON,\\nserialize (sorted keys, no spaces), SHA-256", fillcolor="#f6c9c4"];
  e [label="fam.json  {sha256, body:{version:1, atoms:[...]}}", fillcolor="#e8f1fb"];
  f [label="import state \\"fam.json\\" as kin  (use.ov)"];
  g [label="state/load.py: recompute hash, version, shape,\\nground and sorted atoms; refuse otherwise (E208)", fillcolor="#f6c9c4"];
  h [label="facts with origin import:kin, label {{}}\\n(stated facts: never rules, never 'derived here')"];
  i [label="answers in use.ov rest on those facts\\ntrust stays {kernel}; nothing is upgraded", fillcolor="#d8efdf"];
  a -> b -> c -> d -> e -> f -> g -> h -> i;
""")


def fig_approvals() -> str:
    return G("""
  agent [label="agent (Claude Code)\\nprepares approval/<packet> branch,\\nchanges staged, approvals/<packet>.md", fillcolor="#e8f1fb"];
  dry [label="python -m openverifiers.bench.gold_gate --staged\\n(dry run) + full tests"];
  packet [label="approval packet (reports/APPROVAL_PACKET_*.md)\\nreviewer-classified meaning lines"];
  founder [label="founder reads packet,\\nruns scripts/founder_approve.sh <packet>\\nin own terminal", fillcolor="#fbe7c6"];
  refuse [label="script refuses agent/CI env,\\nnon-tty, .pub keys, ssh-agent keys\\n(speed bump, not security)"];
  sign [label="one SSH-signed commit with trailers\\nMeaning-Approved-By / Gold-Change-Approved-By / Ratifies", fillcolor="#fbe7c6"];
  gate [label="gold_gate.py: trailer counts only if commit is\\nsigned by a key in .approvers/allowed_signers\\n(read from the PARENT commit), principal founder", fillcolor="#f6c9c4"];
  ci [label="CI on every push + reproduce.sh\\nover the whole history"];
  ok [label="gold / meaning change accepted", fillcolor="#d8efdf"];
  bad [label="unsigned or wrongly signed approval,\\nor unapproved meaning/gold line: FAIL", fillcolor="#eeeeee"];
  agent -> dry -> packet -> founder -> refuse -> sign -> gate; ci -> gate; gate -> ok [label="valid"]; gate -> bad [label="else"];
""")


def fig_mcp() -> str:
    return G("""
  call [label="agent wants to call tool T on target X\\n(JSON-RPC tools/call check_tool_call)", fillcolor="#e8f1fb"];
  nm [label="T and X lowercase identifiers?", shape=diamond, style=filled, fillcolor=white];
  u1 [label="unknown (names must be lowercase identifiers)", fillcolor="#eeeeee"];
  named [label="both named in the policy file?", shape=diamond, style=filled, fillcolor=white];
  nh0 [label="needs_human, trust [] (no verdict claimed)", fillcolor="#fbe7c6"];
  scen [label="build scenario: fact request(T, X);\\nPROVE refused / needs_human / permitted\\n(run_file: lower, evaluate, check)"];
  r [label="refused, trust [kernel]", fillcolor="#f6c9c4"];
  nh [label="needs_human, trust [kernel]", fillcolor="#fbe7c6"];
  p [label="permitted, trust [kernel]", fillcolor="#d8efdf"];
  u2 [label="unknown (policy decides nothing)", fillcolor="#eeeeee"];
  call -> nm; nm -> u1 [label="no"]; nm -> named [label="yes"]; named -> nh0 [label="no"]; named -> scen [label="yes"];
  scen -> r [label="refused PROVEN"]; scen -> nh [label="else needs_human PROVEN"]; scen -> p [label="else permitted PROVEN"]; scen -> u2 [label="else"];
""")


OKQL_MODES = [
    ("PROVE", "IMPLEMENTED", "v1"), ("CHECK x IS T", "IMPLEMENTED", "v1"),
    ("FIND / LIMIT", "IMPLEMENTED", "v1"), ("PROVE UNIQUE", "IMPLEMENTED", "v1"),
    ("COUNT", "IMPLEMENTED", "v1"), ("WHY", "IMPLEMENTED", "v1"), ("WHY NOT lit", "IMPLEMENTED", "v1"),
    ("WHAT IF RETRACT/ASSUME", "IMPLEMENTED", "v1"), ("COUNTEREXAMPLE", "IMPLEMENTED", "v1"),
    ("IN / USING state / UNDER", "PLANNED", "MP §5.1"), ("NEAR / DEPENDS ON / AUDIT", "PLANNED", "MP §5.1"),
    ("PROPAGATE", "PLANNED", "v2"), ("COMPUTE", "PLANNED", "v2"), ("OPTIMIZE / PARETO", "PLANNED", "v2"),
    ("WHY NOT option / WHAT WOULD IT TAKE / SENSITIVITY / TRADE", "PLANNED", "v2"),
    ("PLAN FROM .. TO .. (OVProver)", "PLANNED", "v2"), ("EXPLAIN / AT LEVEL / LANG", "PLANNED", "v3"),
    ("AS json|dot|prose", "PLANNED", "MP §5.1"),
]


def fig_okql() -> str:
    col = {"IMPLEMENTED": IMPL, "PLANNED": PLAN}
    out = ['  q [label="query text\\n(query ... inside a .ov file)", fillcolor="#e8f1fb"];',
           '  parse [label="grammar.lark okql rule\\n-> lang/ast.py"];',
           '  split [label="rule query or object query?\\n(objects/compile.py is_object_query)", shape=diamond, style=filled, fillcolor=white];',
           '  rule [label="QueryPlan -> query rule in RawOV\\n(lower/lower.py) -> checked model\\n-> checker/verdict.py"];',
           '  obj [label="ObjPlan -> objects/engine.py\\n-> records -> checker/objects.py"];',
           '  out [label="one verdict + trust_base\\n(text printed by runner.render)", fillcolor="#d8efdf"];',
           "  q -> parse -> split; split -> rule [label=rules]; split -> obj [label=classes]; rule -> out; obj -> out;"]
    out.append('  subgraph cluster_m { label="modes (green: implemented as of bd2ed44, purple: planned)"; style=rounded;')
    for i, (m, st, rel) in enumerate(OKQL_MODES):
        out.append(f'    m{i} [label="{esc(m)}\\n{rel}", fillcolor="{col[st]}"];')
    out.append("  }")
    out.append("  m0 -> q [style=invis];")
    return G("\n".join(out), extra=", newrank=true")


def fig_prover() -> str:
    return G("""
  t [label="target T { must g1, g2; prefer p }\\n(parsed and checked today; nothing consumes it)", fillcolor="#e8f1fb"];
  and1 [label="AND: g1 and g2", shape=box, style="filled", fillcolor="#e2dcf7"];
  or1 [label="OR: rules whose head unifies with g1", shape=ellipse, style="filled", fillcolor="#e2dcf7"];
  or2 [label="OR: rules for g2", shape=ellipse, style="filled", fillcolor="#e2dcf7"];
  r1 [label="rule r1: body b1, b2", fillcolor="#e2dcf7"];
  r2 [label="rule r2: body b3", fillcolor="#e2dcf7"];
  ab [label="abduction: open leaves become\\ncandidate assumptions (minimal sets)", fillcolor="#e2dcf7"];
  prop [label="proposers: search, constraint (z3/MaxSAT),\\nLLM drafts (untrusted)", fillcolor="#e2dcf7"];
  score [label="scoring: fewest assumptions, cost,\\n'prefer' goals, size", fillcolor="#e2dcf7"];
  prog [label="candidate OV program / plan", fillcolor="#e2dcf7"];
  kernel [label="ov run: lower -> evaluate -> trace checker\\n(the kernel decides; the prover cannot write OVState)", fillcolor="#f6c9c4"];
  gap [label="gap report: which must-goals remain\\nUNKNOWN and the missing antichain", fillcolor="#e2dcf7"];
  ok [label="PROVEN plan + trace", fillcolor="#d8efdf"];
  t -> and1; and1 -> or1; and1 -> or2; or1 -> r1; or1 -> r2; r1 -> ab; r2 -> ab; or2 -> ab; ab -> prop -> score -> prog -> kernel;
  kernel -> ok [label="all must PROVEN"]; kernel -> gap [label="otherwise"]; gap -> prop [style=dashed, label="retry"];
""")


ROADMAP = [("v1", "Bedrock", "trust: kernel, checker, OV + objects, OKQL core, exams, agent gate", "now (exit partial: C7)"),
           ("v2", "Engine", "PROPAGATE, goals, OPTIMIZE/PARETO, procedures, OVProver PLAN, NDC", ""),
           ("v3", "Lens", "OV-Prose, EXPLAIN, OV-Paper, LSP, SAT, fallacies", ""),
           ("v4", "Atlas", "registry, theory mappings, adapters, 1M facts, olympiad", ""),
           ("v5", "Sentinel", "agent justification protocol, enterprise, TypeScript SDK, LifeOS", ""),
           ("v6", "Frontier", "ODEs, Lagrangian, 3-body, relativity", "")]


def fig_roadmap() -> str:
    out = []
    for i, (v, n, what, now) in enumerate(ROADMAP):
        fill = PART if now else PLAN
        out.append(f'  r{i} [label="{v} {n}\\n{wrap(what, 34)}{chr(92) + "n" + esc(now) if now else ""}", fillcolor="{fill}"];')
        if i:
            out.append(f"  r{i - 1} -> r{i};")
    return G("\n".join(out), rankdir="LR")


# ============================================================================ figures: case studies


def q11_result() -> Any:
    return run_file("examples/chem/q11.ov")


def fig_dag_q11() -> str:
    res = q11_result()
    tp = write_trace("q11", res, "q11")
    a = res.answers[0]
    v = a.bindings[0][1]
    return proof_dag(tp, v.proof, "q11, FIND ?A, ?C, ?D: proof read back from build/traces/q11.jsonl")


def fig_dag_q11_refuted() -> str:
    res = q11_result()
    tp = write_trace("q11", res, "q11")
    v = res.answers[2].detail
    return proof_dag(tp, v.proof, "q11, PROVE optically_active(add(C, HCN)): the refutation (27 steps)")


def fig_dag_push() -> str:
    res = run_file("benchmarks/physics/push_block/case.ov")
    tp = write_trace("push_block", res, "push_block_s")
    v = res.answers[0].bindings[0][1]
    return proof_dag(tp, v.proof, "push_block, FIND ?m: every step's label carries {frictionless}")


def obj_dag(res_answer: Any, title: str) -> str:
    a = res_answer
    out = []
    recs = a.records
    used = list(getattr(a, "used_hyps", ()) or ())
    for i, s in enumerate(a.steps):
        fill = "#f6c9c4" if ("[checker]" in s or "[kernel" in s) else ("#fbe7c6" if "z3" in s else "#f4f4f4")
        short = s if len(s) < 160 else s[:157] + "..."
        out.append(f'  s{i} [label="{wrap(short, 58)}", fillcolor="{fill}"];')
        if i:
            out.append(f"  s{i - 1} -> s{i};")
    for j, h in enumerate(sorted(set(used))):
        out.append(f'  h{j} [label="{esc(h)}", fillcolor="#e8f1fb", fontsize=8];')
        k = next((i for i, s in enumerate(a.steps) if "certificate" in s), len(a.steps) - 1)
        out.append(f"  h{j} -> s{k};")
    kinds = ", ".join(sorted({str(r.get("kind")) for r in recs})) or "none"
    out.append(f'  v [label="{a.verdict}  trust {{{", ".join(sorted(a.trust_base))}}}\\n'
               f'{len(recs)} record(s) re-checked by checker/objects.py: {esc(kinds)}", fillcolor="#d8efdf"];')
    out.append(f"  s{len(a.steps) - 1} -> v;")
    out.append(f'  labelloc="t"; label="{esc(title)}";')
    return G("\n".join(out))


def fig_dag_square() -> str:
    res = run_file("examples/geometry/square.ov")
    return obj_dag(res.objects[1], "square.ov, PROVE UNIQUE ?p: engine steps, in order")


JEE = "benchmarks/exams/jee2025/jee2025-phys-p2q9/case.ov"


def fig_dag_jee() -> str:
    res = run_file(JEE)
    return obj_dag(res.objects[0], "JEE 2025 phys p2q9: hypotheses used by the uniqueness certificate")


def fig_dag_decay() -> str:
    res = run_file("tests/v1/transcendental.ov")
    a = next(x for x in res.classes if x.title == "theorem Decay.rate_law")
    return obj_dag(a, "Decay.rate_law: d/dt (N0 exp(-k t)) = -k N0 exp(-k t)")


MCP_POLICY = "drafts/policies/repo_policy.ov"


def mcp_scenario(tool: str, target: str) -> Any:
    """The scenario mcp_gate.decide builds (mcp_gate.py:72-77), run in-process."""
    from openverifiers.objects.engine import Settings
    from openverifiers.runner import run_file as rf
    policy = ROOT / MCP_POLICY
    pkg = re.search(r"^\s*package\s+([\w.]+)", policy.read_text(), re.M).group(1)  # type: ignore[union-attr]
    source = (f"package gate_request\nimport {pkg}\nscenario gate uses {pkg} {{\n"
              f"  fact request({tool}, {target})\n  query PROVE refused({tool}, {target})\n"
              f"  query PROVE needs_human({tool}, {target})\n"
              f"  query PROVE permitted({tool}, {target})\n}}\n")
    path = policy.parent / "__gate_request__.ov"
    return rf(path, source=source, files={str(path)}, settings=Settings(drafts=True))


def fig_dag_mcp() -> str:
    res = mcp_scenario("push", "main")
    tp = write_trace("mcp_push_main", res, "gate")
    v = res.answers[0].detail
    return proof_dag(tp, v.proof, "tool-call gate: request(push, main) is refused (proof from the trace)")


def fig_dag_mcp_ok() -> str:
    res = mcp_scenario("open_pr", "feature")
    tp = write_trace("mcp_open_pr", res, "gate")
    v = res.answers[2].detail
    return proof_dag(tp, v.proof, "tool-call gate: request(open_pr, feature) is permitted")


def fig_walkthrough() -> str:
    import hashlib

    from openverifiers.raw.canon import program_to_json
    res = q11_result()
    lw = res.lowered[0]
    pj = json.dumps(program_to_json(lw.program), sort_keys=True)
    tp = write_trace("q11", res, "q11")
    tr = tp.read_text()
    p = lw.program
    src = (ROOT / "examples/chem/q11.ov").read_text()
    return G(f"""
  a [label="examples/chem/q11.ov\\n{len(src.splitlines())} lines, imports chem.organic", fillcolor="#e8f1fb"];
  b [label="RawOV program (scenario q11)\\n{len(p.facts)} facts, {len(p.rules)} rules, {len(p.domains)} domains, {len(p.worlds)} world decls\\ncanonical JSON {len(pj):,} bytes, sha256 {hashlib.sha256(pj.encode()).hexdigest()[:12]}..", fillcolor="#e8f1fb"];
  c [label="OVTrace build/traces/q11.jsonl\\n{len(tr.splitlines()) - 1} steps + header", fillcolor="#e8f1fb"];
  d [label="checker/check.py accepted the trace\\n(else nothing is reported)", fillcolor="#f6c9c4"];
  e [label="4 answers: PROVEN, PROVEN {{single_major}},\\nREFUTED, UNKNOWN (WHAT IF)", fillcolor="#d8efdf"];
  f [label="OVState (ov state ... --scenario q11)\\nunconditional atoms + SHA-256", fillcolor="#e8f1fb"];
  a -> b [label="lang/ + lower/"]; b -> c [label="kernel/evaluate.py"]; c -> d -> e; d -> f;
""", rankdir="LR")


# ============================================================================ figures: evaluation


def exam_rows(strict: bool) -> list[dict[str, Any]]:
    p = N.dir / ("exam_strict.json" if strict else "exam.json")
    d = json.loads(p.read_text())
    return d.get("problems") or d.get("results") or []


def svg_bars(title: str, groups: list[tuple[str, dict[str, int]]], cats: list[tuple[str, str]],
             total: int | None = None) -> str:
    W, bar, gap, left, top = 640, 22, 12, 150, 34
    H = top + len(groups) * (bar + gap) + 40
    mx = total or max(sum(v.values()) for _, v in groups) or 1
    sc = (W - left - 30) / mx
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica" font-size="11">',
           f'<text x="{left}" y="18" font-size="12" font-weight="bold">{title}</text>']
    for i, (g, vals) in enumerate(groups):
        y = top + i * (bar + gap)
        out.append(f'<text x="{left - 6}" y="{y + 15}" text-anchor="end">{g}</text>')
        x = left
        for c, color in cats:
            n = vals.get(c, 0)
            if n:
                w = n * sc
                out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar}" fill="{color}" stroke="white"/>')
                out.append(f'<text x="{x + w / 2:.1f}" y="{y + 15}" text-anchor="middle" fill="black">{n}</text>')
                x += w
    ly = top + len(groups) * (bar + gap) + 10
    lx = left
    for c, color in cats:
        out.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}"/>'
                   f'<text x="{lx + 14}" y="{ly + 9}">{c}</text>')
        lx += 14 + 7 * len(c) + 18
    out.append("</svg>")
    return "\n".join(out)


EXAM_CATS = [("solved", "#3c9d5d"), ("wrong", "#c0392b"), ("unknown", "#999999"),
             ("error", "#e67e22"), ("not_formalized", "#c9c2ea")]


def subj(pid: str) -> str:
    return {"phys": "physics", "chem": "chemistry", "math": "mathematics"}.get(pid.split("-")[1], "?")


def fig_jee() -> str:
    groups = []
    for strict in (False, True):
        rows = exam_rows(strict)
        by: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in rows:
            by[subj(r["id"])][r["outcome"]] += 1
        for s in ("physics", "chemistry", "mathematics"):
            groups.append((f"{s} ({'--strict' if strict else 'default'})", dict(by[s])))
    return svg_bars("JEE Advanced 2025, 30 drawn problems: outcome per subject (reproduce.sh exam.json)",
                    groups, EXAM_CATS, 10)


def fig_tcb() -> str:
    v = N.v
    groups = [("main", {"used": int(v["tcb.main"]), "headroom": int(v["tcb.main_cap"]) - int(v["tcb.main"])}),
              ("raw/formula.py", {"used": int(v["tcb.formula"]), "headroom": int(v["tcb.formula_cap"]) - int(v["tcb.formula"])}),
              ("exact unit A", {"used": int(v["tcb.exact"]), "headroom": int(v["tcb.exact_cap"]) - int(v["tcb.exact"])}),
              ("total", {"used": int(v["tcb.total"]), "headroom": int(v["tcb.total_cap"]) - int(v["tcb.total"])})]
    return svg_bars("Trusted code lines against the D-030 caps (reproduce.sh tcb.txt)", groups,
                    [("used", "#c0392b"), ("headroom", "#e8e8e8")])


def fig_bench() -> str:
    rows = json.loads(N.v.get("bench.suites", "[]"))
    groups = []
    for r in rows:
        name = r.get("suite", "?")
        try:
            groups.append((name, {"pass": int(r.get("passed", 0)), "fail": int(r.get("cases", 0)) - int(r.get("passed", 0))}))
        except ValueError:
            continue
    if not groups:
        B.fail("bench chart: no suites in summary.csv")
    return svg_bars("ov bench (default): cases matching gold per suite (reproduce.sh bench/summary.csv)",
                    groups, [("pass", "#3c9d5d"), ("fail", "#c0392b")])


MILESTONE = re.compile(r"(v1 M0|v1 M1|M1b|Hygiene|C[1-7]\b|checkpoint|MASTERPLAN|Approve packet|D-0\d\d|exit report|Gold: first|First benchmark|OVState|MCP|W3|M-CAP)", re.I)


def milestones() -> list[tuple[str, str, str]]:
    log = B.git("log", "--reverse", "--format=%h|%ad|%s", "--date=short", "1f9c42b^..HEAD", "--",
                ".", ":(exclude)docs/masterbook", ":(exclude)scripts/build_masterbook.py")
    out = []
    for line in log.splitlines():
        h, d, s = line.split("|", 2)
        if MILESTONE.search(s):
            out.append((h, d, s))
    return out


def fig_timeline() -> str:
    ms = milestones()
    keep = [m for m in ms if re.search(r"M0|M1:|M1b|Hygiene|First benchmark|W3:|MASTERPLAN|C[1-7]|exit report|Approve packet|OVState", m[2])]
    out = []
    for i, (h, d, s) in enumerate(keep):
        out.append(f'  t{i} [label="{d}  {h}\\n{wrap(s, 48)}", fillcolor="{IMPL if "exit" not in s else PART}"];')
        if i:
            out.append(f"  t{i - 1} -> t{i};")
    return G("\n".join(out), extra=", ranksep=0.15")


def fig_gold_first() -> str:
    case = "benchmarks/physics/push_block"
    log = B.git("log", "--reverse", "--format=%h|%ad|%s", "--date=iso", "--", f"{case}/expected.json",
                f"{case}/case.ov")
    out = []
    for i, line in enumerate(log.splitlines()[:6]):
        h, d, s = line.split("|", 2)
        files = B.git("show", "--name-only", "--format=", h, "--", case).split()
        out.append(f'  c{i} [label="{h}  {d[:16]}\\n{wrap(s, 50)}\\nfiles: {esc(", ".join(Path(f).name for f in files))}", '
                   f'fillcolor="{"#fbe7c6" if any(f.endswith("expected.json") for f in files) and not any(f.endswith(".ov") for f in files) else "#e8f1fb"}"];')
        if i:
            out.append(f"  c{i - 1} -> c{i};")
    return G("\n".join(out))


# ============================================================================ lowering diagrams


def rule_graph(path: str, lo: int, hi: int, title: str, also: tuple[str, ...] = ()) -> str:
    from openverifiers.lang.check import load
    from openverifiers.lower.lower import lower
    env = load(ROOT / path)
    lw = lower(env, None)[0]
    p = lw.program
    rules = [r for r in p.rules if (r.span and Path(r.span.file).resolve() == (ROOT / path).resolve()
             and lo <= r.span.line <= hi) or any(r.id.startswith(a) for a in also)]
    heads: dict[str, list[str]] = defaultdict(list)
    for r in rules:
        heads[r.head.key].append(r.id)
    out = []
    from openverifiers.raw.program import Naf, Pos, effective_body
    for r in rules:
        out.append(f'  "{r.id}" [label="{esc(r.id)}\\nhead {esc(r.head.key)}", fillcolor="#f4f4f4"];')
        for lit in effective_body(r, p):
            if isinstance(lit, Pos | Naf):
                for src in heads.get(lit.atom.key, []):
                    style = ' [style=dashed, color="#c0392b", label="not"]' if isinstance(lit, Naf) else ""
                    out.append(f'  "{src}" -> "{r.id}"{style};')
    out.append(f'  labelloc="t"; label="{esc(title)}";')
    return G("\n".join(out), rankdir="LR")


def fig_lower_q11() -> str:
    return rule_graph("examples/chem/q11.ov", 3, 14,
                      "q11.ov: the rules lowering generates for unknowns A, B, C, D (rule -> rule it feeds)")


def fig_lower_classes() -> str:
    from openverifiers.lang.check import load
    env = load(PKG / "packages" / "math" / "geometry.ov")
    cl = env.objects
    out = []
    for name in ("Quadrilateral", "Parallelogram", "Rectangle", "Rhombus", "Square"):
        d = cl.defs[name]
        own = [n for n, _ in d.invariants if n.startswith(name + ".")]
        out.append(f'  {name} [label="{name}\\nown: {esc(", ".join(n.split(".", 1)[1] for n in own) or "-")}\\n'
                   f'flattened invariants: {len(d.invariants)}", fillcolor="#e8f1fb"];')
        for _a in cl.ancestors.get(name, ())[:]:
            pass
    for name, parents in (("Parallelogram", ["Quadrilateral"]), ("Rectangle", ["Parallelogram"]),
                          ("Rhombus", ["Parallelogram"]), ("Square", ["Rectangle", "Rhombus"])):
        for pa in parents:
            out.append(f"  {name} -> {pa} [label=extends];")
    sq = cl.defs["Square"]
    out.append(f'  inv [label="Square, flattened (ancestors first, each once):\\n{esc(chr(10).join(n for n, _ in sq.invariants))}", '
               'shape=note, fillcolor="#fff7e0"];'.replace("\n", "\\n"))
    out.append("  Square -> inv [style=dotted];")
    return G("\n".join(out), rankdir="BT")


def fig_lower_newton() -> str:
    from openverifiers.lang.check import load
    from openverifiers.lower.lower import lower
    env = load(ROOT / "benchmarks/physics/push_block/case.ov")
    p = lower(env, None)[0].program
    from openverifiers.rawtext import dump_rule
    out = ['  ax [label="law newton2(b: Body, F: Force):\\n  net_force(b, F) -> F = b.mass * b.accel\\n(mechanics.ov:20-21)", fillcolor="#e8f1fb"];']
    for r in p.rules:
        if r.id.startswith("physics.mechanics.newton2"):
            out.append(f'  "{r.id}" [label="{wrap(B.rel(dump_rule(r)).split(" span(")[0], 60)}"];')
            out.append(f'  ax -> "{r.id}" [label="solve for {r.id.split("#")[-1]}"];')
    return G("\n".join(out), rankdir="LR")


# ============================================================================ generated tables


def tbl(header: list[str], rows: list[list[str]], cols: str | None = None) -> str:
    c = cols or "(" + ", ".join(["auto"] * len(header)) + ")"
    cells = [f"[#strong({B.ts(h)})]" for h in header]
    for r in rows:
        cells += [f"[{x}]" for x in r]
    return f"#table(columns: {c}, " + ", ".join(cells) + ")"


def tx(s: str) -> str:
    """Plain text into Typst content (escaped)."""
    return "#" + "{" + B.ts(s) + "}"


def code(s: str) -> str:
    return "#raw(" + B.ts(s) + ")"


def gen_tcb() -> str:
    main, _units, exact = tcb_files()
    rows = []
    for f in main:
        rows.append([code(f), "main", tx(N.get(f"tcb.file.{f}"))])
    rows.append([tx("main unit total"), "", f"#num({B.ts(N.get('tcb.main'))}) / {N.get('tcb.main_cap')}"])
    rows.append([code("raw/formula.py"), "own unit", f"#num({B.ts(N.get('tcb.formula'))}) / {N.get('tcb.formula_cap')}"])
    rows.append([code(", ".join(e.removeprefix("raw/") for e in exact)), "unit A (exact arithmetic)",
                 f"#num({B.ts(N.get('tcb.exact'))}) / {N.get('tcb.exact_cap')}"])
    rows.append([tx("all trusted code"), "headline (D-030)", f"#num({B.ts(N.get('tcb.total'))}) / {N.get('tcb.total_cap')}"])
    return tbl(["file or unit", "unit", "code lines (no blanks, comments, docstrings)"], rows,
               "(2fr, 1fr, 1.4fr)")


def gen_modules() -> str:
    _edges, sizes = module_graph()
    main, units, exact = tcb_files()
    trusted = {f.replace("/", ".").removesuffix(".py").removesuffix(".__init__"): f for f in [*main, *units, *exact]}
    rows = []
    for m in sorted(sizes):
        t = "TRUSTED" if m in trusted else ""
        unit = ("main" if trusted.get(m) in main else "formula" if trusted.get(m) in units else
                "unit A" if trusted.get(m) in exact else "")
        path = "src/openverifiers/" + ("__init__.py" if m == "openverifiers" else (
            m.replace(".", "/") + (".py" if (PKG / (m.replace(".", "/") + ".py")).exists() else "/__init__.py")))
        doc = ast.get_docstring(ast.parse((ROOT / path).read_text())) or ""
        first = doc.strip().splitlines()[0] if doc.strip() else ""
        rows.append([code(path.removeprefix("src/openverifiers/")), tx(str(sizes[m])),
                     (f"#text(fill: rgb(\"#c0392b\"), weight: \"bold\")[{t}] {unit}" if t else ""),
                     tx(first[:110])])
    return tbl(["module", "lines", "trust", "first docstring line"], rows, "(1.5fr, 0.5fr, 0.7fr, 3.3fr)")


def gen_packages() -> str:
    rows = []
    for p in ov_packages():
        rows.append([code(p["name"]), tx(p["version"]), "packages/" if p["approved"] else "drafts/",
                     tx(str(p["classes"])), tx(str(p["theorems"])), tx(str(p["laws"])),
                     tx(str(p["axioms"])), tx(", ".join(p["imports"]) or "-")])
    return tbl(["package", "ver", "where", "classes", "thm/lemma", "law", "axiom/def", "imports"], rows,
               "(1.6fr, 0.4fr, 0.7fr, 0.5fr, 0.5fr, 0.4fr, 0.5fr, 1.6fr)")


def gen_audits() -> str:
    out = []
    totals = {"kernel": 0, "all": 0}
    for p in ov_packages():
        if not p["approved"]:
            continue
        d = AUDITS[p["name"]]
        kinds: dict[str, int] = defaultdict(int)
        for a in d["axioms"]:
            kinds[a["kind"]] += 1
        th = d["theorems"]
        st: dict[str, int] = defaultdict(int)
        for t in th:
            st[t["status"]] += 1
            if t["status"] == "PROVEN" and t.get("trust") == ["kernel"]:
                totals["kernel"] += 1
            totals["all"] += 1
        out.append([code(p["name"]), tx(", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))),
                    tx(", ".join(f"{k} {v}" for k, v in sorted(st.items())) or "-"),
                    tx(str(sum(1 for t in th if t.get("trust") == ["kernel"]))),
                    tx(f"{d.get('ratio', '')}"), tx(f"{d.get('claim_ratio', '')}"),
                    tx(f"{d.get('strict_claim_ratio', '')}")])
    N.v["audit.kernel"] = str(totals["kernel"])
    N.v["audit.all"] = str(totals["all"])
    return tbl(["package", "axioms by kind", "theorems by status", "at {kernel}", "axiom ratio",
                "claim ratio", "strict claim"], out, "(1.5fr, 2fr, 1.5fr, 0.6fr, 0.6fr, 0.6fr, 0.6fr)")


def gen_theorems() -> str:
    rows = []
    for p in ov_packages():
        if not p["approved"]:
            continue
        d = AUDITS[p["name"]]
        for t in d["theorems"]:
            rows.append([code(t["name"]), tx(t["status"]), code("{" + ", ".join(t.get("trust", [])) + "}"),
                         code(f"{p['file'].rsplit('/', 1)[0]}/{t['where']}")])
    return tbl(["theorem", "status", "trust_base", "where"], rows, "(2.2fr, 0.7fr, 1.6fr, 1.8fr)")


def gen_decisions() -> str:
    rows = []
    for line in (ROOT / "MASTERPLAN.md").read_text().splitlines():
        m = re.match(r"\|\s*(D-\d{3}[a-z]?)\s*\|\s*([\d-]+)\s*\|(.*)\|(.*)\|\s*$", line)
        if m:
            rows.append([code(m.group(1)), tx(m.group(2)), tx(md_plain(m.group(3).strip())),
                         tx(md_plain(m.group(4).strip()))])
    return tbl(["ID", "date", "decision (verbatim from MASTERPLAN.md §11)", "decided by"], rows,
               "(0.5fr, 0.7fr, 4fr, 1.1fr)")


def md_plain(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).replace("`", "")


def md_to_typst(md: str) -> str:
    """A small Markdown subset (headings, bullets, bold, code, tables) to Typst, escaped."""
    out: list[str] = []
    table: list[list[str]] = []

    def inline(s: str) -> str:
        parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", s)
        r = []
        for p in parts:
            if p.startswith("`") and p.endswith("`") and len(p) > 1:
                r.append(code(p[1:-1]))
            elif p.startswith("**") and p.endswith("**"):
                r.append("#strong[" + tx(p[2:-2]) + "]")
            elif p:
                r.append(tx(p))
        return "".join(r)

    def flush() -> None:
        if table:
            hdr, body = table[0], [r for r in table[1:] if not set("".join(r)) <= set("-: ")]
            n = len(hdr)
            out.append(tbl([re.sub(r"[*`]", "", h) for h in hdr], [[inline(c) for c in (r + [""] * n)[:n]] for r in body]))
            table.clear()

    for line in md.splitlines():
        if line.strip().startswith("|"):
            table.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        flush()
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"\n#strong[{tx(m.group(2))}]\n" if lvl > 1 else "")
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            ind = len(m.group(1)) // 2
            out.append("  " * ind + "- " + inline(m.group(2)))
            continue
        if re.match(r"^\s+\S", line) and out and out[-1].lstrip().startswith("- "):
            out[-1] += " " + inline(line.strip())
            continue
        out.append(inline(line) if line.strip() else "")
    flush()
    return "\n".join(out)


def gen_limitations() -> str:
    return md_to_typst((ROOT / "KNOWN_LIMITATIONS.md").read_text())


CLI_RUNS = [("ov --help", 0), ("ov run", 2), ("ov run --help", 2), ("ov exam --help", 0),
            ("ov audit", 2), ("ov audit --help", 2), ("ov state", 2), ("ov state --help", 1),
            ("ov bench --help", 2), ("ov gate --help", 0), ("ov query x.ov", 2),
            ("ov examples/chem/q11.ov", 2)]


def gen_cli() -> str:
    out = []
    for cmd, code_ in CLI_RUNS:
        mask = ' @@ mask=File "[^"]*(bin/ov|/lib/python[^"]*)", line [0-9]+' if "state --help" in cmd else ""
        out.append(B.render_run(B.do_run(f"{cmd} @@ exit={code_}{mask}", ARGS)))
    return "\n".join(out)


def lang_doc_codes() -> dict[str, str]:
    out = {}
    for line in (ROOT / "docs" / "LANGUAGE.md").read_text().splitlines():
        m = re.match(r"\|\s*([EW]\d{3})\s*\|\s*(.*?)\s*\|\s*$", line)
        if m:
            out[m.group(1)] = md_plain(m.group(2))
    return out


def source_codes() -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for p in sorted(PKG.rglob("*.py")):
        if p.relative_to(PKG).parts[0] in ("legacy", "m1"):
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for c in re.findall(r'"([EW]\d{3})"', line):
                out[c].append(f"{p.relative_to(ROOT)}:{i}")
    return out


MECH = ("package m @0.1\ntype Body { mass: Mass, accel: Accel }\npredicate net_force(b: Body, F: Force) world open\n"
        "axiom newton2(b: Body, F: Force): net_force(b, F) -> F = b.mass * b.accel\n")
POINT = "type Point { x: Real, y: Real }\n"
#: Files that trigger each code, after the snippets in tests/v1/test_lang.py,
#: test_objects.py, test_diagnostics.py and test_lemma_scope.py. Written to
#: build/work/errors/ at build time (never committed: several declare packages,
#: and committed package files fall under the meaning gate).
ERROR_FIXTURES: dict[str, dict[str, str]] = {
    "E101": {"E101.ov": "scenario s { fact p(a) b }\n"},
    "E102": {"E102.ov": "scenario s { fact p(a) $ }\n"},
    "E103": {"E103.ov": "scenario s { fact p(3 furlong) }\n"},
    "E201": {"E201.ov": "scenario s { fact frob(a) }\n"},
    "E202": {"E202.ov": "type T\nscenario s { entity a: T  entity a: T }\n"},
    "E203": {"E203.ov": "import nowhere.at_all\n"},
    "E204": {"E204.ov": MECH + "test x { scenario s uses m { entity c: Body  fact c.colour = 2 } }\n"},
    "E205": {"E205.ov": MECH + "test x { scenario s uses m { entity c: Body  fact net_force(c) } }\n"},
    "E206": {"E206.ov": "scenario s {\n  tolerance 2\n}\n"},
    "E207": {"E207.ov": POINT + "fact type T { property a: Real  derived b: Real = a * 2 }\n"},
    "E208": {"E208.ov": "# strict: run with --strict\npackage p\npredicate f(s: Surface) world open\n"},
    "E301": {"E301.ov": MECH + "test x { scenario s uses m { entity c: Body  fact c.mass = 2 kg + 1 m } }\n"},
    "E302": {"E302.ov": MECH + "test x { scenario s uses m { entity c: Body  fact net_force(c, c) } }\n"},
    "E303": {"E303.ov": MECH + "test x { scenario s uses m { entity c: Body  fact c < c } }\n"},
    "E304": {"E304.ov": "fact type Gas {\n  property p: Pressure\n  property t: Temperature\n  invariant pos: p > 0 t > 0\n}\n"},
    "E401": {"E401.ov": "package p\npredicate q(x: Number) world open\naxiom a(x: Number): q(x) -> x = 1\n"},
    "E402": {"E402.ov": "package p\ntype B { v: Number }\npredicate q(b: B) world open\naxiom a(b: B): q(b) -> b.v ^ 2 = 4\n"},
    "E403": {"E403.ov": "package p\npredicate q(x: Number) world closed\npredicate r(x: Number) world open\naxiom a(x: Number): not q(x) -> r(x)\n"},
    "E404": {"E404.ov": "package p\npredicate q(x: Number) -> {Number} world open\ngenerator g(x: Number) yields Number from q(x)\n"},
    "E405": {"E405.ov": POINT + "fact type T { property v: Set<Point> invariant a: exists w in cycles(v): angle(w[0], w[1], w[2]) = 37 deg }\n"},
    "E406": {"E406.ov": "fact type A extends B { }\nfact type B extends A { }\n"},
    "E407": {"lemmapkg.ov": "package lemmapkg\nfact type Base {\n  property a: Real\n  property b: Real\n  invariant shift: a = b + 1\n  lemma gap: a - b = 1\n}\n",
             "E407.ov": "import lemmapkg\nscenario s uses lemmapkg {\n  query COUNTEREXAMPLE Base.gap\n}\n"},
    "W201": {"W201.ov": "package p\npredicate f(s: Surface) world open\n"},
    "W202": {"W202.ov": POINT + "fact type Q { property vertices: Set<Point>  invariant four: count(vertices) = 4 }\n"
             "fact type S extends Q {\n  invariant shape: exists v in cycles(vertices): all i: dist(v[i], v[i+1]) = dist(v[0], v[1]) > 0\n"
             "  theorem t: exists v in cycles(vertices): dist(v[0], v[2]) = dist(v[1], v[3])\n}\n"},
}


def gen_errors() -> str:
    docs, src = lang_doc_codes(), source_codes()
    codes = sorted(set(docs) | set(src) | set(ERROR_FIXTURES))
    d = B.WORK / "errors"
    d.mkdir(parents=True, exist_ok=True)
    blocks = []
    rows = []
    for c in codes:
        trig = "-"
        if c in ERROR_FIXTURES:
            for fn, text in ERROR_FIXTURES[c].items():
                (d / fn).write_text(text)
            fx = d / f"{c}.ov"
            strict = "--strict " if "strict" in fx.read_text().splitlines()[0] else ""
            cmd = f"ov run {strict}{B.rel(fx)}"
            res = B.do_run(cmd + " @@ exit=" + ("0" if c.startswith("W") else "1"), ARGS)
            if f"[{c}]" not in res["out"]:
                B.fail(f"error fixture {fx.name} did not trigger {c}:\n{res['out']}")
            trig = "yes"
            blocks.append(f"=== {c}\n" + B.listing(B.rel(fx)) + "\n" + B.render_run(res))
        where = src.get(c, [])
        rows.append([code(c), tx(docs.get(c, "(not in docs/LANGUAGE.md)")),
                     tx(f"{len(where)} site(s)" + (f", first {where[0]}" if where else ", never raised")), tx(trig)])
    return tbl(["code", "meaning (docs/LANGUAGE.md)", "raised in src/", "example below"], rows,
               "(0.5fr, 3fr, 2fr, 0.6fr)") + "\n\n" + "\n\n".join(blocks)


def gen_ebnf() -> str:
    rules = lark_rules(GRAMMAR.read_text())
    lines = []
    for n, _inl, e in rules:
        if n.isupper():
            continue
        lines.append(f"{n} ::= {ebnf(parse_expansion(e))} ;")
    return B.listing.__globals__["ts"] and f"#listing({B.ts('generated from src/openverifiers/lang/grammar.lark')}, \"ebnf\", {B.ts(chr(10).join(lines))})"


def gen_okql_ebnf() -> str:
    rules = {n: e for n, _, e in lark_rules(GRAMMAR.read_text())}
    lines = [f"{n} ::= {ebnf(parse_expansion(rules[n]))} ;" for n in
             ("query", "okql", "qvars", "qvar_t", "change", "expect", "conj", "fact_lit", "lit", "cmp")]
    return f"#listing({B.ts('generated from grammar.lark: the OKQL rules')}, \"ebnf\", {B.ts(chr(10).join(lines))})"


def md_section(path: str, start: str, stop: str = "## ") -> str:
    lines = (ROOT / path).read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(start))
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(stop)), len(lines))
    return "\n".join(lines[i + 1: j])


def gen_reports() -> str:
    rows = []
    for p in sorted((ROOT / "reports").glob("*.md")):
        t = p.read_text()
        title = next((ln.lstrip("# ") for ln in t.splitlines() if ln.startswith("#")), "")
        dev = re.search(r"^## .*[Dd]eviation", t, re.M) is not None
        sh = re.search(r"^## .*[Ss]hortcut", t, re.M) is not None
        h = B.git("log", "--diff-filter=A", "--format=%h", "--", str(p.relative_to(ROOT))).split()
        rows.append([code(p.name), tx(title[:90]), code(h[-1] if h else "?"),
                     tx(("deviations " if dev else "") + ("shortcuts" if sh else ""))])
    return tbl(["report", "title", "added in", "has sections"], rows, "(1.7fr, 3fr, 0.6fr, 1fr)")


def gen_deviations() -> str:
    out = []
    for path in ("reports/V1_EXIT_C7_2026-11-23.md",):
        out.append(f"#strong[{tx(path + ': Deviations')}]\n")
        out.append(md_to_typst(md_section(path, "## 5. Deviations")))
        out.append(f"\n#strong[{tx(path + ': Shortcuts found')}]\n")
        out.append(md_to_typst(md_section(path, "## 6. Shortcuts found")))
    return "\n".join(out)


def gen_risks() -> str:
    return md_to_typst(md_section("MASTERPLAN.md", "## 10. Risks", "## 11."))


def gen_jee_blockers() -> str:
    rows = []
    for r in exam_rows(False):
        if r["outcome"] in ("solved",):
            continue
        rows.append([code(r["id"].removeprefix("jee2025-")), tx(r["outcome"]), tx(r.get("category", "")),
                     tx(r.get("note", "")[:400])])
    return tbl(["problem", "outcome", "category", "what blocks it (the exam report's note, verbatim, cut at 400 characters)"],
               rows, "(0.8fr, 0.8fr, 0.8fr, 5fr)")


def gen_jee_table() -> str:
    rows = []
    d0 = {r["id"]: r for r in exam_rows(False)}
    d1 = {r["id"]: r for r in exam_rows(True)}
    for pid in sorted(d0):
        a, b = d0[pid], d1.get(pid, {})
        why = a.get("category") or a.get("note") or a.get("detail") or ""
        rows.append([code(pid.removeprefix("jee2025-")), tx(a.get("outcome", "?") + (" (prov.)" if a.get("provisional") else "")),
                     tx(b.get("outcome", "?")), tx(str(a.get("answer", ""))[:28]),
                     tx(str(a.get("official", a.get("gold", "")))[:28]), tx(str(why)[:80])])
    return tbl(["problem", "default (+drafts)", "--strict", "OV answer", "official", "category / note"],
               rows, "(0.9fr, 0.9fr, 0.7fr, 1fr, 1fr, 2.6fr)")


def gen_timeline() -> str:
    rows = [[code(h), tx(d), tx(s[:120])] for h, d, s in milestones()]
    return tbl(["commit", "date", "subject"], rows, "(0.6fr, 0.7fr, 4fr)")


def gen_bench_table() -> str:
    rows = json.loads(N.v.get("bench.suites", "[]"))
    rs = json.loads(N.v.get("bench_strict.suites", "[]"))
    sm = {r.get("suite"): r for r in rs}
    if not rows:
        return tx("(no bench summary)")
    keys = list(rows[0].keys())
    body = []
    for r in rows:
        body.append([tx(str(r.get(k, ""))) for k in keys] + [tx(str(sm.get(r.get("suite"), {}).get("passed", "")))])
    return tbl([*keys, "pass (--strict)"], body)


def gen_diff_table() -> str:
    d = json.loads((N.dir / "differential.json").read_text())
    rows = []

    def walk(prefix: str, x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(x, (int, float, str)) and not isinstance(x, bool):
            rows.append([code(prefix), tx(str(x)[:60])])
    walk("", d)
    return tbl(["field of differential.json", "value"], rows[:60], "(2fr, 2fr)")


def gen_lowering_rawov_q11() -> str:
    from openverifiers.lang.check import load
    from openverifiers.lower.lower import lower
    from openverifiers.raw.program import Program
    from openverifiers.rawtext import dump
    env = load(ROOT / "examples/chem/q11.ov")
    p = lower(env, None)[0].program
    sel = Program(p.worlds[:0], tuple(f for f in p.facts if f.span and f.span.file.endswith("q11.ov")),
                  tuple(r for r in p.rules if r.span and r.span.file.endswith("q11.ov")), ())
    return f"#listing({B.ts('RawOV of examples/chem/q11.ov (items whose span is in q11.ov; printed by rawtext.dump)')}, \"rawov\", {B.ts(B.rel(dump(sel)))})"


def gen_trace_excerpt() -> str:
    res = q11_result()
    tp = write_trace("q11", res, "q11")
    lines = tp.read_text().splitlines()
    pick = [lines[0]] + [ln for ln in lines[1:] if '"id": 232,' in ln or '"id": 240,' in ln]
    return f"#listing({B.ts('build/traces/q11.jsonl: the header and steps 232 and 240 (written by raw/trace.py dumps)')}, \"json\", {B.ts(chr(10).join(pick))})"


def gen_program_json_excerpt() -> str:
    from openverifiers.raw.canon import program_to_json
    res = run_file("benchmarks/physics/push_block/case.ov")
    pj = program_to_json(res.lowered[0].program)
    small = {k: (v[:3] if isinstance(v, list) else v) for k, v in pj.items()}
    s = B.rel(json.dumps(small, sort_keys=True, indent=1))
    return f"#listing({B.ts('canonical program JSON of push_block (raw/canon.py program_to_json; first 3 rows of each list)')}, \"json\", {B.ts(s)})"


def gen_state_excerpt() -> str:
    d = json.loads((B.WORK / "fam.json").read_text()) if (B.WORK / "fam.json").exists() else None
    if d is None:
        B.fail("state excerpt: run the ov state command first (order in chapter)")
        return ""
    s = json.dumps({"sha256": d["sha256"], "body": {"version": d["body"]["version"],
                                                    "atoms": d["body"]["atoms"][:2]}}, indent=1)
    return f"#listing({B.ts('build/work/fam.json (first 2 of ' + str(len(d['body']['atoms'])) + ' atoms)')}, \"json\", {B.ts(s)})"


def gen_labels_trace() -> str:
    labels_run()
    fig_labels()
    t = (B.TRACES / "labels.jsonl").read_text()
    return f"#listing({B.ts('build/traces/labels.jsonl (the OVTrace of examples/labels.rawov)')}, \"json\", {B.ts(t)})"


def gen_labels_verdicts() -> str:
    from openverifiers.checker import verdict
    from openverifiers.rawtext import parse_atom
    r = labels_run()
    rows = []
    for q in ("wet(lawn)", "slippery(lawn)", "dry(lawn)", "warn(lawn)"):
        a = parse_atom(q)
        for ctx in (frozenset({"rain", "sprinkler"}), frozenset({"rain"}), frozenset({"sprinkler"}), frozenset()):
            v = verdict(r.model, a, ctx)
            name = type(v).__name__.upper()
            extra = ""
            if hasattr(v, "assumptions"):
                extra = "{" + ", ".join(("" if s else "not ") + n for n, s in sorted(v.assumptions)) + "}"
            rows.append([code(q), code("{" + ", ".join(sorted(ctx)) + "}"), tx(name), code(extra or getattr(v, "reason", ""))])
    return tbl(["query", "context C", "verdict", "environment used / reason"], rows)


def gen_records_excerpt() -> str:
    res = run_file(JEE)
    a = res.objects[0]
    rec = next((r for r in a.records if r.get("kind") != "model"), a.records[-1])
    s = json.dumps(rec, sort_keys=True)
    s = s[:2400] + (" ... (truncated by the book; " + str(len(s)) + " characters in all)" if len(s) > 2400 else "")
    return f"#listing({B.ts('the uniqueness certificate record behind JEE phys p2q9 (ObjAnswer.records, as JSON)')}, \"json\", {B.ts(s)})"


def gen_blueprint() -> str:
    from openverifiers.paper import blueprints
    res = run_file("tests/v1/transcendental.ov")
    bp = [b for b in blueprints(res) if b["theorem"] == "Decay.rate_law"]
    s = B.rel(json.dumps(bp[0], indent=1))
    return f"#listing({B.ts('openverifiers.paper.blueprints() for Decay.rate_law (the v3 OV-Paper hooks)')}, \"json\", {B.ts(s)})"


def gen_sdk() -> str:
    script = ROOT / "docs/masterbook/examples/sdk_demo.py"
    r = B.do_run(f"python {B.rel(script)}", ARGS)
    return B.listing(B.rel(script)) + "\n" + B.render_run(r)


# ============================================================================ side-by-side lowerings


def side(left_title: str, left: str, right_title: str, right: str) -> str:
    B.STATS["listings"] += 2
    return f"#side({B.ts(left_title)}, {B.ts(left)}, {B.ts(right_title)}, {B.ts(right)})"


def file_lines(path: str, lo: int, hi: int) -> str:
    return "\n".join((ROOT / path).read_text().splitlines()[lo - 1: hi])


def rawov_in_span(path: str, lo: int, hi: int, scenario_file: str | None = None,
                  id_prefix: tuple[str, ...] = ()) -> str:
    from openverifiers.lang.check import load
    from openverifiers.lower.lower import lower
    from openverifiers.raw.program import Program
    from openverifiers.rawtext import dump
    env = load(ROOT / (scenario_file or path))
    lws = lower(env, None)
    target = (ROOT / path).resolve()
    out = []
    for lw in lws:
        p = lw.program

        def inside(x: Any) -> bool:
            return (x.span is not None and Path(x.span.file).resolve() == target
                    and lo <= x.span.line <= hi) or any(x.id.startswith(a) for a in id_prefix)
        sel = Program(tuple(w for w in p.worlds if any(r.head.key == w.pred for r in p.rules if inside(r))),
                      tuple(f for f in p.facts if inside(f)), tuple(r for r in p.rules if inside(r)),
                      tuple(d for d in p.domains if inside(d)))
        txt = dump(sel).strip()
        if txt:
            out.append(f"% scenario {lw.scenario}\n{txt}")
    s = "\n".join(dict.fromkeys(out))
    s = re.sub(r' span\("[^"]*", (\d+), \d+, (\d+), \d+\)', r" span(L\1-L\2)", B.rel(s))
    return s


def classdef_text(file: str, name: str, props: bool = True) -> str:
    from openverifiers.lang.check import load
    from openverifiers.rawtext import dump_term
    env = load(ROOT / file)
    d = env.objects.defs[name]
    out = [f"% compiled ClassDef {d.name} (objects/compile.py -> raw/formula.py ClassDef)"]
    if props:
        out.append("props: " + ", ".join(d.props))
    for n, t in d.invariants:
        out.append(f"invariant {n}:\n  {dump_term(t)}")
    for n, t in d.theorems:
        out.append(f"theorem {n}:\n  {dump_term(t)}")
    return "\n".join(out)


def low_class() -> str:
    return side("src/openverifiers/packages/physics/mechanics.ov:28-41",
                file_lines("src/openverifiers/packages/physics/mechanics.ov", 28, 41),
                "compiled class (dump_term of each formula)",
                classdef_text("src/openverifiers/packages/physics/mechanics.ov", "ConstantAcceleration"))


def low_newton() -> str:
    return side("src/openverifiers/packages/physics/mechanics.ov:17-21",
                file_lines("src/openverifiers/packages/physics/mechanics.ov", 17, 21),
                "RawOV rules from push_block's program (ids physics.mechanics.newton2*)",
                rawov_in_span("src/openverifiers/packages/physics/mechanics.ov", 20, 21,
                              scenario_file="benchmarks/physics/push_block/case.ov"))


def low_transformation() -> str:
    f = "docs/masterbook/examples/kitchen.ov"
    return side(f + ":1-17", file_lines(f, 1, 17), "RawOV (items whose span is in kitchen.ov)",
                rawov_in_span(f, 1, 17))


def low_generator() -> str:
    return side("examples/chem/q11.ov:3-9 (+ chem/organic.ov:67)",
                file_lines("examples/chem/q11.ov", 3, 9) + "\n# chem.organic:\n" +
                file_lines("src/openverifiers/packages/chem/organic.ov", 67, 67),
                "RawOV generated for the unknowns (span in q11.ov:3-9)",
                rawov_in_span("examples/chem/q11.ov", 3, 9))


def low_assume() -> str:
    f = "benchmarks/physics/push_block/case.ov"
    return side(f + ":20-29", file_lines(f, 20, 29), "RawOV (span in lines 20-29)",
                rawov_in_span(f, 20, 29))


def low_inherit() -> str:
    f = "src/openverifiers/packages/math/geometry.ov"
    return side(f + ":34-78", file_lines(f, 34, 78), "compiled Square: ancestors' invariants first, each once",
                classdef_text(f, "Square", props=True))


def low_pattern() -> str:
    from openverifiers.lang.check import load
    from openverifiers.rawtext import dump_term
    f = "examples/geometry/square.ov"
    env = load(ROOT / f)
    plans = list(env.objects.plans.values())
    out = []
    for pl in plans:
        out.append(f"% ObjPlan kind={pl.kind}, class {pl.cls.name}")
        for k, t in pl.props.items():
            out.append(f"prop {k} = {dump_term(t)}")
        for k, vs in pl.unknowns.items():
            out.append(f"unknown ?{k} -> coordinates {', '.join(v.name for v in vs)}")
    sq = env.objects.defs["Square"]
    shape = next(t for n, t in sq.invariants if n == "Square.shape")
    out.append("% Square.shape compiled:\n" + dump_term(shape))
    return side(f + ":10-29", file_lines(f, 10, 29), "compiled query plans + the shape invariant",
                "\n".join(out))


def low_units() -> str:
    f = "benchmarks/physics/mass_in_grams/case.ov"
    return side(f, (ROOT / f).read_text().strip(), "RawOV: quantities as rationals with dimension vectors",
                rawov_in_span(f, 1, 12, id_prefix=("physics.mechanics.newton2",)))


def low_extends() -> str:
    f = "docs/masterbook/examples/kitchen.ov"
    return side(f + ":7-17", file_lines(f, 7, 17), "RawOV of scenario more (inherits base's facts)",
                rawov_in_span(f, 7, 17))


def low_check_rule() -> str:
    f = "docs/masterbook/examples/checks.ov"
    return side(f, (ROOT / f).read_text().strip(), "RawOV: functional clash rule and a check rule",
                rawov_in_span(f, 1, 40))


def low_jee() -> str:
    return side(JEE + ":12-25", file_lines(JEE, 12, 25), "compiled class (component invariants included)",
                classdef_text(JEE, "ChargedConductingSphere", props=True))


def low_decay() -> str:
    f = "tests/v1/transcendental.ov"
    return side(f + ":5-14", file_lines(f, 5, 14), "compiled class Decay", classdef_text(f, "Decay"))


def gen_mcp_rawov() -> str:
    from openverifiers.raw.program import Program
    from openverifiers.rawtext import dump
    res = mcp_scenario("push", "main")
    p = res.lowered[0].program
    keep = ("agent.workflow.gate_", "gate.", "repo_policy.", "ov.query.gate")
    sel = Program((), tuple(f for f in p.facts if f.id.startswith(keep)),
                  tuple(r for r in p.rules if r.id.startswith(keep)), ())
    t = re.sub(r' span\("[^"]*", (\d+), \d+, (\d+), \d+\)', r" span(L\1-L\2)", B.rel(dump(sel)))
    return (f"#listing({B.ts('RawOV of the gate scenario for push/main (rules of agent.workflow named gate_*, the policy facts, the request)')}, "
            f"\"rawov\", {B.ts(t)})")


FIGDEFS: dict[str, tuple[Any, str, str, str, bool]] = {
    "layers": (fig_layers, "The ten-layer architecture (MP §3) with the status of each layer as of the stamped commit", "conceptual, statuses from this book's chapters", "100%", False),
    "pipeline": (fig_pipeline, "The pipeline OV -> RawOV -> OVTrace -> checker -> verdicts and OVState, with the module that does each step", "conceptual; module paths real", "88%", False),
    "trust": (fig_trust, "The trust boundary: the trusted files are exactly those counted by scripts/tcb_size.py", "generated from scripts/tcb_size.py's file lists", "100%", False),
    "imports": (fig_imports, "Module import graph of src/openverifiers (legacy/ and m1/ omitted); trusted modules in red", "generated from the code (ast imports)", "100%", False),
    "imports_pkg": (fig_imports_pkg, "Import graph between subpackages; edge label = number of module-level imports", "generated from the code", "70%", False),
    "tower": (fig_tower, "The package theory tower: every .ov package and its imports (green approved, purple draft)", "generated from the package files", "100%", False),
    "audit_dag": (fig_audit_dag, "ov audit --dag ConstantAcceleration.suvat_timeless: what a theorem rests on", "generated from ov audit --json", "80%", False),
    "labels": (fig_labels, "Label propagation in a small RawOV program: each step's cumulative label", "generated from build/traces/labels.jsonl", "100%", False),
    "strata": (fig_strata, "Stratification of the same program: closed-world 'not' edges (red) go strictly upward", "generated by kernel/strata.py", "70%", False),
    "verdicts": (fig_verdicts, "How checker/verdict.py turns labels into one of four verdicts", "conceptual, following checker/verdict.py:108-135", "70%", False),
    "cert_flow": (fig_cert_flow, "The certificate check flow: untrusted finder, trusted normal form", "conceptual", "80%", False),
    "qpi": (fig_qpi, "The Q(pi) sign decision on x = 22/7 - pi, with the enclosure computed in this build", "generated by raw/qpi.py and raw/interval.py", "90%", False),
    "exp_rules": (fig_exp_rules, "The exp/ln differential ring of the trusted normal form; sin/cos is D-033 (not at this commit)", "conceptual", "75%", False),
    "find_seq": (fig_find_seq, "The object-layer FIND sequence: solve, re-check, block, re-solve, unsat", "generated from the engine's steps for square.ov", "70%", False),
    "state_life": (fig_state_life, "The OVState lifecycle: save, hash, load, import; trust never rises", "conceptual; module paths real", "60%", False),
    "approvals": (fig_approvals, "The gold/meaning gate and the signed-approval flow (D-032)", "conceptual", "70%", False),
    "mcp": (fig_mcp, "The MCP tool-call gate decision flow (mcp_gate.py decide)", "conceptual, following mcp_gate.py:60-85", "75%", False),
    "okql": (fig_okql, "The OKQL query lifecycle and the modes, implemented and planned", "conceptual", "100%", False),
    "prover": (fig_prover, "The OVProver AND-OR design (masterplan v2): nothing here is built", "conceptual", "75%", True),
    "roadmap": (fig_roadmap, "The masterplan release roadmap and where the project stands", "conceptual, from MASTERPLAN.md §1, §7", "100%", False),
    "dag_q11": (fig_dag_q11, "Proof DAG of q11's first answer", "generated from the OVTrace file", "100%", False),
    "dag_q11_ref": (fig_dag_q11_refuted, "Proof DAG of q11's refutation of optical activity", "generated from the OVTrace file", "100%", False),
    "dag_push": (fig_dag_push, "Proof DAG of push_block's mass under {frictionless}", "generated from the OVTrace file", "75%", False),
    "dag_square": (fig_dag_square, "The square's fourth vertex: the UNIQUE answer's evidence chain", "generated from the engine's answer", "75%", False),
    "dag_jee": (fig_dag_jee, "JEE 2025 phys p2q9: the uniqueness certificate and the hypotheses it used", "generated from the engine's answer and record", "100%", False),
    "dag_decay": (fig_dag_decay, "The decay law: the certificate proving the closed form solves dN/dt = -kN", "generated from the engine's answer", "75%", False),
    "dag_mcp": (fig_dag_mcp, "Tool-call gate: why push to main is refused", "generated from the OVTrace file", "75%", False),
    "dag_mcp_ok": (fig_dag_mcp_ok, "Tool-call gate: why open_pr on feature is permitted", "generated from the OVTrace file", "100%", False),
    "walkthrough": (fig_walkthrough, "q11 end to end: the artefacts and their sizes in this build", "generated from the real artefacts", "100%", False),
    "jee": (fig_jee, "JEE Advanced 2025 results, default and --strict", "generated from reproduce.sh exam.json / exam_strict.json", "100%", False),
    "tcb_chart": (fig_tcb, "Trusted code against its caps", "generated from reproduce.sh tcb.txt", "90%", False),
    "bench_chart": (fig_bench, "ov bench, default run, per suite", "generated from reproduce.sh bench/summary.csv", "90%", False),
    "timeline": (fig_timeline, "Milestones from M0 to the stamped commit", "generated from git log", "62%", False),
    "gold_first": (fig_gold_first, "Gold first and alone: the history of benchmarks/physics/push_block", "generated from git log", "70%", False),
    "lower_q11": (fig_lower_q11, "Lowering of q11's unknowns: which generated rule feeds which", "generated from the lowered program", "100%", False),
    "lower_classes": (fig_lower_classes, "The quadrilateral hierarchy of math.geometry and Square's flattened invariants (diamond rule)", "generated from the compiled classes", "80%", False),
    "lower_newton": (fig_lower_newton, "One law, two rules: newton2 solved for each slot", "generated from the lowered program", "100%", False),
}
for gid, (cap, _) in RAIL_GROUPS.items():
    FIGDEFS[gid] = ((lambda g=gid: rail_group(g)), f"Railroad diagrams: {cap}", "generated from grammar.lark", "100%", False)

GENDEFS = {
    "tcb": gen_tcb, "modules": gen_modules, "packages": gen_packages, "audits": gen_audits,
    "theorems": gen_theorems, "decisions": gen_decisions, "limitations": gen_limitations,
    "cli": gen_cli, "errors": gen_errors, "ebnf": gen_ebnf, "okql_ebnf": gen_okql_ebnf,
    "jee_table": gen_jee_table, "timeline": gen_timeline, "bench_table": gen_bench_table,
    "diff_table": gen_diff_table, "rawov_q11": gen_lowering_rawov_q11,
    "trace_excerpt": gen_trace_excerpt, "program_json": gen_program_json_excerpt,
    "state_excerpt": gen_state_excerpt, "labels_trace": gen_labels_trace,
    "labels_verdicts": gen_labels_verdicts, "records_excerpt": gen_records_excerpt,
    "blueprint": gen_blueprint, "sdk": gen_sdk, "mcp_rawov": gen_mcp_rawov,
    "reports": gen_reports, "deviations": gen_deviations, "risks": gen_risks,
    "jee_blockers": gen_jee_blockers,
}
LOWERDEFS = {
    "class": low_class, "newton": low_newton, "transformation": low_transformation,
    "generator": low_generator, "assume": low_assume, "inherit": low_inherit,
    "pattern": low_pattern, "jee": low_jee, "decay": low_decay, "units": low_units, "extends": low_extends, "checks": low_check_rule,
}
