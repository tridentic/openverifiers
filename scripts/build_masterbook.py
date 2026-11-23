#!/usr/bin/env python3
"""Build the OpenVerifiers Masterbook (docs only; never imported by the package).

    python scripts/build_masterbook.py [--accept] [--ci] [--run-repro] [--no-pdf]

What it does, in order:

1. **Numbers.** Reads the outputs of ``reproduce.sh`` for the *code commit* (the
   last commit that touched anything outside the book's own files). They are kept
   in ``docs/masterbook/repro/<code-commit>/``. If that folder is missing, the
   script copies ``docs/masterbook/build/repro/`` when its stamp names the same
   commit, or runs ``bash reproduce.sh docs/masterbook/build/repro`` (25-35 min)
   with ``--run-repro``. Under ``--ci`` a missing folder is an error.
2. **Runs.** Every ``{{run:CMD}}`` marker in the chapter sources is executed
   (from the repository root, with this virtualenv's ``ov`` and ``python``). Its
   exit code must match, and its normalised output must equal the committed
   snapshot in ``docs/masterbook/snapshots/``. ``--accept`` (re)writes snapshots;
   ``--ci`` refuses to create missing ones.
3. **Diagrams.** Graphviz sources are generated from real data (module imports,
   package imports, OVTrace files written by real runs, ``ov audit``, the
   grammar), rendered to SVG with ``dot``.
4. **Chapters.** ``docs/masterbook/src/*.typ`` are expanded: every marker is
   replaced by Typst code. Unknown markers, unfilled placeholders, a badge with
   no evidence marker, a PLANNED badge with no masterplan reference, a cited
   file or line range that does not exist, a commit that is not in the history,
   or a test that does not exist all fail the build.
5. **PDF.** Typst compiles ``docs/masterbook/build/OpenVerifiers_Masterbook_<head>.pdf``
   with only its embedded fonts (so every machine gives the same layout).

Markers (inline unless noted):

    {{badge:IMPLEMENTED|PARTIAL|PLANNED}}   {{num:KEY}}            {{mp:TEXT}}
    {{src:PATH[:A-B]}}   {{test:PATH::NAME}}   {{commit:HASH}}   {{report:PATH}}
    {{listing:PATH[:A-B][:LANG]}}   (block)  a real file excerpt
    {{run:CMD [@@ exit=N] [@@ head=N] [@@ stdin=PATH] [@@ mask=REGEX]}}  (block)
    {{fig:NAME}}  (block)   {{gen:NAME}}  (block)   {{lower:NAME}}  (block)
"""

from __future__ import annotations

import argparse
import ast
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from collections import defaultdict
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "docs" / "masterbook"
SRC = BOOK / "src"
SNAP = BOOK / "snapshots"
REPRO_STORE = BOOK / "repro"
BUILD = BOOK / "build"
GEN = BUILD / "gen"
FIG = BUILD / "fig"
CH = BUILD / "ch"
TRACES = BUILD / "traces"
WORK = BUILD / "work"
PKG = ROOT / "src" / "openverifiers"
BIN = Path(sys.executable).parent
BOOK_PATHS = ("docs/masterbook", "scripts/build_masterbook.py", "Makefile",
              ".github/workflows/masterbook.yml", "pyproject.toml")

sys.path.insert(0, str(ROOT / "src"))

ERRORS: list[str] = []
STATS: dict[str, Any] = defaultdict(int)
FIGURES_USED: list[str] = []


def fail(msg: str) -> None:
    ERRORS.append(msg)


# ============================================================================ shell / git


def sh(cmd: str, *, stdin: str | None = None, check: bool = True, timeout: int = 1800
       ) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{BIN}{os.pathsep}{env.get('PATH', '')}"
    env["PYTHONHASHSEED"] = "0"
    env.pop("PYTHONPATH", None)
    return subprocess.run(["bash", "-c", cmd], cwd=ROOT, env=env, input=stdin, text=True,
                          capture_output=True, check=check, timeout=timeout)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True,
                          check=True).stdout.strip()


def head_commit() -> str:
    return git("rev-parse", "--short=7", "HEAD")


def code_commit() -> str:
    """The last commit that changed anything outside the book's own files."""
    excl = [f":(exclude){p}" for p in BOOK_PATHS]
    return git("log", "-1", "--format=%h", "--abbrev=7", "--", ".", *excl)


def commit_exists(h: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{h}^{{commit}}"], cwd=ROOT,
                          capture_output=True).returncode == 0


# ============================================================================ numbers


def flatten(v: dict[str, str], prefix: str, x: Any) -> None:
    if isinstance(x, dict):
        for k, y in x.items():
            flatten(v, f"{prefix}.{k}", y)
    elif isinstance(x, list):
        v[prefix + ".len"] = str(len(x))
        v[prefix] = ", ".join(map(str, x)) if all(not isinstance(y, (dict, list)) for y in x) else ""
    elif x is not None:
        v[prefix] = f"{x:,}" if isinstance(x, int) and not isinstance(x, bool) and abs(x) >= 10000 else str(x)


class Numbers:
    """Every number in the book, read from reproduce.sh's outputs."""

    def __init__(self, folder: Path) -> None:
        self.dir = folder
        self.v: dict[str, str] = {}
        self._parse()

    def text(self, name: str) -> str:
        p = self.dir / name
        if not p.exists():
            fail(f"numbers: {p} missing")
            return ""
        return p.read_text()

    def _parse(self) -> None:
        v = self.v
        # TCB
        for line in self.text("tcb.txt").splitlines():
            m = re.match(r"\s*(\d+)\s+(\S+\.py)$", line)
            if m:
                v[f"tcb.file.{m.group(2)}"] = m.group(1)
            m = re.match(r"\s*(\d+)\s+trusted code lines \(limit (\d+)\); (\d+) physical", line)
            if m:
                v["tcb.main"], v["tcb.main_cap"], v["tcb.main_physical"] = m.groups()
            m = re.match(r"\s*(\d+)\s+raw/formula.py.*limit (\d+)", line)
            if m:
                v["tcb.formula"], v["tcb.formula_cap"] = m.groups()
            m = re.match(r"\s*(\d+)\s+exact-arithmetic unit.*limit (\d+)", line)
            if m:
                v["tcb.exact"], v["tcb.exact_cap"] = m.groups()
            m = re.match(r"\s*(\d+)\s+all trusted code \(limit (\d+)\)", line)
            if m:
                v["tcb.total"], v["tcb.total_cap"] = m.groups()
        # tests and coverage
        t = self.text("tests_v1.txt")
        m = re.search(r"(\d+) passed", t)
        v["tests.v1_passed"] = m.group(1) if m else "?"
        m = re.search(r"(\d+) deselected", t)
        v["tests.v1_deselected"] = m.group(1) if m else "0"
        t = self.text("tests_all.txt")
        m = re.search(r"(\d+) passed", t)
        v["tests.all_passed"] = m.group(1) if m else "?"
        m = re.search(r"(\d+) skipped", t)
        v["tests.all_skipped"] = m.group(1) if m else "0"
        m = re.search(r"(\d+) failed", t)
        v["tests.all_failed"] = m.group(1) if m else "0"
        m = re.search(r"(\d+) deselected", t)
        v["tests.all_deselected"] = m.group(1) if m else "0"
        t = self.text("coverage.txt")
        m = re.search(r"(\d+)%", t)
        v["coverage.trusted"] = (m.group(1) + "%") if m else "?"
        # bench
        for key, f in (("bench", "bench.txt"), ("bench_strict", "bench_strict.txt")):
            t = self.text(f)
            v[f"{key}.line"] = t.strip()
            m = re.search(r"(\d+)\s*/\s*(\d+)", t)
            if m:
                v[f"{key}.pass"], v[f"{key}.total"] = m.groups()
            m = re.search(r"(\d+) false PROVEN", t)
            v[f"{key}.false_proven"] = m.group(1) if m else "?"
        self._bench_suites()
        # exam
        for key, f in (("exam", "exam.json"), ("exam_strict", "exam_strict.json")):
            p = self.dir / f
            if p.exists():
                flatten(v, key, json.loads(p.read_text()).get("summary", {}))
        # differential
        p = self.dir / "differential.json"
        if p.exists():
            flatten(v, "diff", json.loads(p.read_text()))
        # mutants
        t = self.text("mutants.txt")
        v["mutants.raw"] = t.strip()
        dicts = [ln for ln in t.splitlines() if ln.startswith("{")]
        for i, ln in enumerate(dicts):
            try:
                d = ast.literal_eval(ln)
            except (ValueError, SyntaxError):
                continue
            for k, x in d.items():
                v[f"mutants.{i}.{k}"] = str(x)
        m = re.search(r"(\d+) passed", t)
        v["mutants.tests_passed"] = m.group(1) if m else "?"
        # faithfulness, gold gate
        v["faithfulness.line"] = self.text("faithfulness.txt").strip()
        m = re.search(r"(\d+) error", v["faithfulness.line"])
        v["faithfulness.errors"] = m.group(1) if m else "?"
        m = re.search(r"(\d+) warning", v["faithfulness.line"])
        v["faithfulness.warnings"] = m.group(1) if m else "?"
        g = self.text("gold_gate.txt").strip()
        v["gold_gate.line"] = g.splitlines()[-1] if g else "(no output)"
        v["gold_gate.lines"] = str(len(g.splitlines()))
        lg = (self.dir / "repro.log")
        if lg.exists():
            m = re.search(r"real\s+(\d+)m([\d.]+)s", lg.read_text()) or re.search(
                r"(\d+):([\d.]+) total", lg.read_text())
            if m:
                v["repro.minutes"] = str(round(int(m.group(1)) + float(m.group(2)) / 60))

    def _bench_suites(self) -> None:
        for key, sub in (("bench", "bench"), ("bench_strict", "bench-strict")):
            p = self.dir / sub / "summary.csv"
            if not p.exists():
                continue
            import csv
            rows = list(csv.DictReader(p.open()))
            self.v[f"{key}.suites"] = json.dumps(rows)
            for r in rows:
                s = r.get("suite") or r.get("Suite") or ""
                for k, x in r.items():
                    self.v[f"{key}.suite.{s}.{k}"] = x

    def get(self, key: str) -> str:
        if key not in self.v:
            fail(f"numbers: unknown key '{key}'")
            return "??"
        return self.v[key]


def ensure_repro(args: argparse.Namespace, cc: str) -> Path:
    store = REPRO_STORE / cc
    if store.exists():
        return store
    built = BUILD / "repro"
    stamp = built / "STAMP"
    if built.exists() and stamp.exists() and stamp.read_text().split()[0] == cc:
        shutil.copytree(built, store, ignore=shutil.ignore_patterns("*.jsonl"))
        log = BUILD / "repro.log"
        if log.exists():
            shutil.copy(log, store / "repro.log")
        return store
    if args.ci:
        fail(f"no reproduce.sh outputs for code commit {cc} in {store}")
        return store
    if not args.run_repro:
        fail(f"no reproduce.sh outputs for {cc}: run with --run-repro (25-35 minutes)")
        return store
    print(f"running reproduce.sh for {cc} (25-35 minutes) ...", flush=True)
    built.mkdir(parents=True, exist_ok=True)
    r = sh(f"(time bash reproduce.sh {built.relative_to(ROOT)}) > {BUILD / 'repro.log'} 2>&1",
           check=False, timeout=4 * 3600)
    (built / "STAMP").write_text(f"{cc} exit={r.returncode}\n")
    return ensure_repro(args, cc)


# ============================================================================ typst helpers


def ts(s: str) -> str:
    """A Typst string literal."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "    ")
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", s)
    return '"' + s.replace("\n", "\\n") + '"'


def rel(p: str | Path) -> str:
    s = str(p)
    return s.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")


# ============================================================================ runs


RUNS: dict[str, dict[str, Any]] = {}


def slug(cmd: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", cmd).strip("_")[:70]
    return f"{s}_{hashlib.sha1(cmd.encode()).hexdigest()[:8]}"


def normalise(out: str, mask: str | None) -> str:
    out = out.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")
    out = re.sub(r"/private/tmp/[^\s'\"]+|/tmp/[^\s'\"]+", "<tmp>", out)
    if mask:
        out = re.sub(mask, "<masked>", out)
    return "\n".join(line.rstrip() for line in out.splitlines()).strip("\n") + "\n"


def do_run(spec: str, args: argparse.Namespace) -> dict[str, Any]:
    parts = [p.strip() for p in spec.split("@@")]
    cmd, opts = parts[0], dict(p.split("=", 1) for p in parts[1:])
    key = spec
    if key in RUNS:
        return RUNS[key]
    want = int(opts.get("exit", "0"))
    stdin = (ROOT / opts["stdin"]).read_text() if "stdin" in opts else None
    r = sh(cmd, stdin=stdin, check=False)
    out = r.stdout + (("\n" + r.stderr) if r.stderr.strip() else "")
    norm = normalise(out, opts.get("mask"))
    name = slug(cmd + (" <" + opts["stdin"] if "stdin" in opts else ""))
    snap = SNAP / f"{name}.txt"
    if r.returncode != want:
        fail(f"run: `{cmd}` exited {r.returncode}, expected {want}\n{out[-2000:]}")
    if snap.exists() and not args.accept:
        if snap.read_text() != norm:
            import difflib
            diff = "\n".join(difflib.unified_diff(snap.read_text().splitlines(),
                                                  norm.splitlines(), "snapshot", "now",
                                                  lineterm="", n=1))
            fail(f"run: output of `{cmd}` changed (rerun with --accept if intended):\n"
                 f"{diff[:3000]}")
    elif not snap.exists() and args.ci:
        fail(f"run: no snapshot for `{cmd}` ({snap.name})")
    else:
        SNAP.mkdir(parents=True, exist_ok=True)
        snap.write_text(norm)
    res = {"cmd": cmd, "code": r.returncode, "out": norm, "opts": opts, "snap": snap.name}
    RUNS[key] = res
    STATS["runs"] += 1
    return res


def render_run(res: dict[str, Any]) -> str:
    out = res["out"].rstrip("\n")
    lines = out.splitlines()
    note = ""
    head = res["opts"].get("head")
    if head and len(lines) > int(head):
        note = f"... {len(lines) - int(head)} more lines (full output: snapshots/{res['snap']})"
        out = "\n".join(lines[: int(head)])
    cmd = res["cmd"]
    if "stdin" in res["opts"]:
        cmd += " < " + res["opts"]["stdin"]
    return f"#runbox({ts(cmd)}, {res['code']}, {ts(out)}, {ts(note)})"


# ============================================================================ evidence


def check_src(spec: str) -> str:
    m = re.match(r"(.+?)(?::(\d+)(?:-(\d+))?)?$", spec)
    assert m
    path, a, b = m.group(1), m.group(2), m.group(3)
    p = ROOT / path
    if not p.exists():
        fail(f"evidence: file {path} does not exist")
        return spec
    if a:
        n = len(p.read_text(errors="replace").splitlines()) if p.is_file() else 0
        if int(a) < 1 or int(b or a) > n or int(b or a) < int(a):
            fail(f"evidence: {path} has {n} lines, cited {a}-{b or a}")
    return spec


def check_test(spec: str) -> str:
    path, _, name = spec.partition("::")
    p = ROOT / path
    if not p.exists() or not re.search(rf"^def {re.escape(name)}\b", p.read_text(), re.M):
        fail(f"evidence: test {spec} not found")
    return spec


def check_commit(h: str) -> str:
    if not commit_exists(h):
        fail(f"evidence: commit {h} not in the history")
    return h


MP_TEXT = (ROOT / "MASTERPLAN.md").read_text()


def check_mp(text: str) -> str:
    for d in re.findall(r"D-0\d\d[a-z]?", text):
        if d not in MP_TEXT and d not in ("D-033", "D-034", "D-031b"):
            fail(f"evidence: {d} not in MASTERPLAN.md")
    if not re.search(r"MP|v[1-6]|D-0\d\d", text):
        fail(f"evidence: masterplan reference '{text}' names no release, section or decision")
    return text


# ============================================================================ expansion


MARKER = re.compile(r"\{\{(\w+):(.*?)\}\}")
EVIDENCE_KINDS = {"src", "test", "commit", "run", "mp", "report", "listing", "lower", "num",
                  "gen", "fig"}
GENS: dict[str, Callable[[], str]] = {}
FIGS: dict[str, dict[str, Any]] = {}
LOWERINGS: dict[str, Callable[[], str]] = {}


def listing(spec: str) -> str:
    parts = spec.split(":")
    path, rng, lang = parts[0], (parts[1] if len(parts) > 1 else ""), (
        parts[2] if len(parts) > 2 else "")
    p = ROOT / path
    if not p.exists():
        fail(f"listing: {path} missing")
        return ""
    lines = p.read_text().splitlines()
    if rng:
        a, _, b = rng.partition("-")
        lo, hi = int(a), int(b or a)
        if hi > len(lines):
            fail(f"listing: {path} has {len(lines)} lines, asked {rng}")
        body = "\n".join(lines[lo - 1: hi])
        title = f"{path}:{lo}-{hi}"
    else:
        body, title = "\n".join(lines), path
    if not lang:
        lang = {".ov": "ov", ".py": "python", ".json": "json", ".lark": "lark", ".sh": "bash",
                ".md": "md", ".yml": "yaml", ".jsonl": "json"}.get(p.suffix, "")
    STATS["listings"] += 1
    return f"#listing({ts(title)}, {ts(lang)}, {ts(body)})"


def expand(text: str, name: str, nums: Numbers, args: argparse.Namespace) -> str:
    # 1. author-text checks
    for bad in ("TODO", "TBD", "FIXME", "XXX", "PLACEHOLDER", "lorem"):
        for m in re.finditer(rf"\b{bad}\b", text):
            line = text[: m.start()].count("\n") + 1
            fail(f"{name}:{line}: unfilled placeholder '{bad}'")
    paras = re.split(r"\n\s*\n", text)
    offset = 0
    for para in paras:
        for m in re.finditer(r"\{\{badge:(\w+)\}\}", para):
            kind = m.group(1)
            if kind not in ("IMPLEMENTED", "PARTIAL", "PLANNED"):
                fail(f"{name}: unknown badge {kind}")
            lines = para.splitlines()
            window = para
            if len(lines) > 12:            # a table: the badge's own row (and the next two)
                k = para[: m.start()].count("\n")
                window = "\n".join(lines[max(0, k - 1): k + 3])
            kinds = {x.group(1) for x in MARKER.finditer(window)}
            line = text[: offset + m.start()].count("\n") + 1 if offset >= 0 else 0
            if not (kinds & EVIDENCE_KINDS):
                fail(f"{name}:{line}: badge {kind} without an evidence marker")
            if kind == "PLANNED" and "mp" not in kinds:
                fail(f"{name}:{line}: PLANNED badge without a masterplan reference {{{{mp:..}}}}")
            STATS[f"badge.{kind}"] += 1
        offset += len(para) + 2

    # 2. markers
    def rep(m: re.Match[str]) -> str:
        kind, arg = m.group(1), m.group(2).strip()
        if kind == "badge":
            return f'#{{badge("{arg}")}}'
        if kind == "num":
            return f"#{{num({ts(nums.get(arg))})}}"
        if kind == "src":
            STATS["evidence"] += 1
            return f'#{{ev("src", {ts(check_src(arg))})}}'
        if kind == "report":
            STATS["evidence"] += 1
            return f'#{{ev("report", {ts(check_src(arg))})}}'
        if kind == "test":
            STATS["evidence"] += 1
            return f'#{{ev("test", {ts(check_test(arg))})}}'
        if kind == "commit":
            STATS["evidence"] += 1
            return f'#{{ev("commit", {ts(check_commit(arg))})}}'
        if kind == "mp":
            STATS["evidence"] += 1
            return f'#{{ev("plan", {ts(check_mp(arg))})}}'
        if kind == "cmd":
            return f"#{{raw({ts(arg)})}}"
        if kind == "listing":
            return listing(arg)
        if kind == "run":
            return render_run(do_run(arg, args))
        if kind == "fig":
            if arg not in FIGS:
                fail(f"{name}: unknown figure {arg}")
                return ""
            FIGURES_USED.append(arg)
            return render_fig(arg)
        if kind == "gen":
            if arg not in GENS:
                fail(f"{name}: unknown generated block {arg}")
                return ""
            try:
                return GENS[arg]()
            except Exception as e:           # a generator bug must fail the build
                import traceback
                fail(f"{name}: gen {arg} failed: {e}\n{traceback.format_exc()[-1500:]}")
                return ""
        if kind == "lower":
            if arg not in LOWERINGS:
                fail(f"{name}: unknown lowering {arg}")
                return ""
            try:
                return LOWERINGS[arg]()
            except Exception as e:
                import traceback
                fail(f"{name}: lowering {arg} failed: {e}\n{traceback.format_exc()[-1500:]}")
                return ""
        fail(f"{name}: unknown marker kind '{kind}'")
        return m.group(0)

    out = MARKER.sub(rep, text)
    for m in re.finditer(r"\{\{|\}\}", out.replace("{{{", "")):
        pass
    left = [m.group(0) for m in re.finditer(r"\{\{\w+:", text) if not MARKER.match(
        text, m.start())]
    for x in left:
        fail(f"{name}: unterminated marker {x}")
    return out


# ============================================================================ figures


def dot_to_svg(name: str, dot: str) -> Path:
    FIG.mkdir(parents=True, exist_ok=True)
    (FIG / f"{name}.dot").write_text(dot)
    out = FIG / f"{name}.svg"
    r = subprocess.run(["dot", "-Tsvg", "-o", str(out)], input=dot, text=True,
                       capture_output=True)
    if r.returncode != 0:
        fail(f"figure {name}: dot failed: {r.stderr[:500]}")
    return out


def figure(name: str, caption: str, kind: str, width: str = "100%", planned: bool = False
           ) -> Callable[[Callable[[], str]], Callable[[], str]]:
    """Register a figure. ``kind`` is 'generated from ...' or 'conceptual'."""
    def deco(fn: Callable[[], str]) -> Callable[[], str]:
        FIGS[name] = {"fn": fn, "caption": caption, "kind": kind, "width": width,
                      "planned": planned}
        return fn
    return deco


def render_fig(name: str) -> str:
    f = FIGS[name]
    try:
        content = f["fn"]()
    except Exception as e:
        import traceback
        fail(f"figure {name} failed: {e}\n{traceback.format_exc()[-2000:]}")
        return ""
    if content.lstrip().startswith(("digraph", "graph", "strict")):
        dot_to_svg(name, content)
        path = f"/build/fig/{name}.svg"
    elif content.lstrip().startswith("<svg"):
        FIG.mkdir(parents=True, exist_ok=True)
        (FIG / f"{name}.svg").write_text(content)
        path = f"/build/fig/{name}.svg"
    else:                                    # Typst content (several images)
        return (f"#figbox({content}, {ts(f['caption'])}, {ts(f['kind'])}, "
                f"{'true' if f['planned'] else 'false'}, {ts(name)}) <fig-{name}>")
    return (f"#fig({ts(path)}, {ts(f['caption'])}, {ts(f['kind'])}, {f['width']}, "
            f"{'true' if f['planned'] else 'false'}, {ts(name)}) <fig-{name}>")


# The figure, generator and lowering definitions live in a sibling module so this
# file stays readable.
sys.path.insert(0, str(BOOK / "tools"))


# ============================================================================ main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept", action="store_true", help="rewrite output snapshots")
    ap.add_argument("--ci", action="store_true", help="never create snapshots or numbers")
    ap.add_argument("--run-repro", action="store_true", help="run reproduce.sh if needed")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    for d in (GEN, FIG, CH, TRACES, WORK):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    head, cc = head_commit(), code_commit()
    date = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    repro = ensure_repro(args, cc)
    nums = Numbers(repro) if repro.exists() else Numbers.__new__(Numbers)
    if not repro.exists():
        nums.v, nums.dir = {}, repro
    import masterbook_parts as parts            # figures, generated tables, lowerings
    parts.register(sys.modules[__name__], nums, args)

    meta = {"head": head, "code_commit": cc, "date": date,
            "repro": rel(repro), "python": sys.version.split()[0]}
    (BUILD / "meta.json").write_text(json.dumps(meta, indent=1))

    order = [ln.strip() for ln in (SRC / "book.txt").read_text().splitlines()
             if ln.strip() and not ln.startswith("#")]
    includes = []
    for fname in order:
        text = (SRC / fname).read_text()
        out = expand(text, fname, nums, args)
        (CH / fname).write_text('#import "../template.typ": *\n' + out)
        includes.append(f'#include "ch/{fname}"')
    shutil.copy(SRC / "template.typ", BUILD / "template.typ")
    main_typ = '#import "template.typ": *\n#show: book\n' + "\n".join(includes) + "\n"
    (BUILD / "main.typ").write_text(main_typ)

    STATS["figures"] = len(set(FIGURES_USED))
    STATS["figures_list"] = sorted(set(FIGURES_USED))
    if ERRORS:
        print(f"\nBUILD FAILED: {len(ERRORS)} problem(s)\n", file=sys.stderr)
        for e in ERRORS:
            print(" - " + e, file=sys.stderr)
        return 1
    if args.no_pdf:
        print("expanded; --no-pdf")
        return 0
    import typst
    pdf = BUILD / f"OpenVerifiers_Masterbook_{head}.pdf"
    for old in BUILD.glob("OpenVerifiers_Masterbook_*.pdf"):
        old.unlink()
    try:
        typst.compile(str(BUILD / "main.typ"), output=str(pdf), root=str(BOOK),
                      ignore_system_fonts=True)
    except Exception as e:                   # typst reports source positions
        print(f"typst failed:\n{e}", file=sys.stderr)
        return 1
    pages = None
    if shutil.which("pdfinfo"):
        m = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], text=True,
                                                         capture_output=True).stdout)
        pages = int(m.group(1)) if m else None
    STATS["pages"] = pages
    STATS["pdf"] = rel(pdf)
    (BUILD / "stats.json").write_text(json.dumps(dict(STATS), indent=1, default=str))
    print(json.dumps({k: STATS[k] for k in ("pdf", "pages", "figures", "runs", "listings",
                                             "evidence")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
