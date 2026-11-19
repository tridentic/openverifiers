"""Code-requirements domain pack: a function must satisfy stated requirements.

Fact types
  spec          ``{"function": name, "requirements": {"R1": text, ...}}``
  check_suite   ``{"tests": pytest source}``; each requirement Rk is compiled
                into tests named ``test_Rk_*`` (plain pytest or hypothesis
                properties) that import the function from ``solution``
  source        Python source of the candidate implementation
  check_report  ``{"passed": bool, "results": {"R1": "passed" | "failed" |
                "error" | "skipped" | "missing" | "timeout", ...}}``

Transformations (both hard)
  code.implement   spec -> source. The code is the proposer's own work, so
                   there is no effect; the checker parses it, requires the
                   named top-level function, and refuses a small denylist of
                   modules and builtins (a lint, not a security boundary).
  code.run_checks  spec + source + check_suite -> check_report. Every spec
                   requirement must have at least one test. The effect runs the
                   suite with pytest in a subprocess (``python -I``, temp
                   directory, scrubbed environment, wall-clock timeout, CPU
                   rlimit where available, hypothesis derandomized). The
                   kernel compares the claimed report with the real one.

Predicates
  all_checks_pass          the report says every requirement passed
  requirement_passes       ``args.requirement`` passed

The subprocess is *isolation for honesty, not security*: it keeps a crash or
an infinite loop from taking the checker down, but it does not stop
malicious code from touching the file system. Run untrusted code in a
container.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openverifiers.m1.kernel import DomainPack, Fact, FactType, Precondition, Transformation
from openverifiers.m1.kernel.model import Inputs, Params

TIMEOUT_S = 30.0
_DENY_MODULES = {"os", "sys", "subprocess", "socket", "shutil", "pathlib", "ctypes",
                 "importlib", "multiprocessing", "threading", "signal"}
_DENY_NAMES = {"eval", "exec", "compile", "open", "__import__", "globals", "breakpoint"}

# ---- fact types --------------------------------------------------------------


def _validate_spec(f: Fact) -> str | None:
    v = f.value
    if not isinstance(v, dict) or not isinstance(v.get("function"), str):
        return "spec needs a 'function' name"
    reqs = v.get("requirements")
    if not isinstance(reqs, dict) or not reqs:
        return "spec needs a non-empty 'requirements' mapping"
    return None


def _validate_suite(f: Fact) -> str | None:
    v = f.value
    if not isinstance(v, dict) or not isinstance(v.get("tests"), str):
        return "check_suite needs 'tests' source"
    return None


def _validate_source(f: Fact) -> str | None:
    return None if isinstance(f.value, str) else "source must be a string"


def _validate_report(f: Fact) -> str | None:
    v = f.value
    if not isinstance(v, dict) or not isinstance(v.get("passed"), bool) \
            or not isinstance(v.get("results"), dict):
        return "check_report needs 'passed' (bool) and 'results' (mapping)"
    return None


# ---- code.implement -------------------------------------------------------------


def _static_policy(source: str, function: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"does not parse: {exc.msg} (line {exc.lineno})"
    if not any(isinstance(n, ast.FunctionDef) and n.name == function for n in tree.body):
        return f"no top-level function named {function!r}"
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]]
        if bad := set(mods) & _DENY_MODULES:
            return f"imports denied module(s) {sorted(bad)}"
        if isinstance(node, ast.Name) and node.id in _DENY_NAMES:
            return f"uses denied builtin {node.id!r}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"uses dunder attribute {node.attr!r}"
    return None


def _implement_checker(i: Inputs, p: Params, o: Mapping[str, Fact]) -> str | None:
    return _static_policy(o["source"].value, i["spec"].value["function"])


# ---- code.run_checks ---------------------------------------------------------------


def _limit_cpu() -> None:  # runs in the child before exec (POSIX only)
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (int(TIMEOUT_S), int(TIMEOUT_S)))
    except (ImportError, ValueError, OSError):
        pass


def run_suite(source: str, tests: str, requirement_ids: list[str],
              timeout: float = TIMEOUT_S) -> dict[str, Any]:
    """Run ``tests`` against ``source`` in a fresh subprocess; summarize per
    requirement. Deterministic for deterministic tests (hypothesis is run
    derandomized)."""
    with tempfile.TemporaryDirectory(prefix="ov-checks-") as tmp:
        d = Path(tmp)
        (d / "solution.py").write_text(source)
        (d / "test_requirements.py").write_text(tests)
        (d / "conftest.py").write_text(
            "from hypothesis import settings\n"
            "settings.register_profile('ov', derandomize=True, deadline=None,"
            " database=None)\nsettings.load_profile('ov')\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "PYTHONHASHSEED": "0",
               "PYTHONDONTWRITEBYTECODE": "1"}
        cmd = [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--junitxml=report.xml", "test_requirements.py"]
        try:
            proc = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True,
                                  timeout=timeout,
                                  preexec_fn=_limit_cpu if os.name == "posix" else None)
        except subprocess.TimeoutExpired:
            return {"passed": False, "results": dict.fromkeys(requirement_ids, "timeout")}
        status: dict[str, str] = {}
        xml = d / "report.xml"
        if xml.exists():
            for case in ET.parse(xml).iter("testcase"):
                parts = case.get("name", "").split("_")
                rid = parts[1] if len(parts) > 1 and parts[0] == "test" else ""
                if rid not in requirement_ids:
                    continue
                if case.find("failure") is not None:
                    outcome = "failed"
                elif case.find("error") is not None:
                    outcome = "error"
                elif case.find("skipped") is not None:
                    outcome = "skipped"
                else:
                    outcome = "passed"
                # a requirement passes only if every one of its tests passes
                if status.get(rid, "passed") == "passed":
                    status[rid] = outcome
        results = {rid: status.get(rid, "missing") for rid in requirement_ids}
        if proc.returncode not in (0, 1) and all(v == "missing" for v in results.values()):
            results = dict.fromkeys(requirement_ids, "error")  # collection failed
        return {"passed": proc.returncode == 0 and all(v == "passed" for v in results.values()),
                "results": results}


def _suite_covers_spec(i: Inputs, p: Params) -> str | None:
    tests = i["checks"].value["tests"]
    names = {n.name for n in ast.walk(ast.parse(tests)) if isinstance(n, ast.FunctionDef)}
    missing = [r for r in i["spec"].value["requirements"]
               if not any(n.startswith(f"test_{r}_") for n in names)]
    return f"no test compiled for requirement(s) {missing}" if missing else None


def _run_checks(i: Inputs, p: Params) -> Mapping[str, Fact]:
    rids = list(i["spec"].value["requirements"])
    report = run_suite(i["source"].value, i["checks"].value["tests"], rids)
    return {"report": Fact("_", "check_report", value=report)}


# ---- predicates ---------------------------------------------------------------------


def _all_pass(f: Fact, args: Params) -> str | None:
    failing = {k: v for k, v in f.value["results"].items() if v != "passed"}
    if f.value["passed"] and not failing:
        return None
    return f"not passing: {failing}" if failing else "suite reported failure"


def _requirement_passes(f: Fact, args: Params) -> str | None:
    got = f.value["results"].get(args["requirement"], "missing")
    return None if got == "passed" else f"{args['requirement']} is {got}"


PACK = DomainPack(
    name="code_requirements",
    fact_types={
        "spec": FactType("spec", validate=_validate_spec),
        "check_suite": FactType("check_suite", validate=_validate_suite),
        "source": FactType("source", validate=_validate_source),
        "check_report": FactType("check_report", validate=_validate_report),
    },
    transformations={t.id: t for t in [
        Transformation("code.implement", "hard", {"spec": "spec"}, {"source": "source"},
                       checker=_implement_checker,
                       doc="write the function the spec names (static checks only)"),
        Transformation("code.run_checks", "hard",
                       {"spec": "spec", "source": "source", "checks": "check_suite"},
                       {"report": "check_report"},
                       preconditions=(Precondition("suite_covers_spec", _suite_covers_spec),),
                       effect=_run_checks,
                       doc="run the compiled requirement checks in a subprocess"),
    ]},
    predicates={"all_checks_pass": _all_pass, "requirement_passes": _requirement_passes},
)
