"""Lint-health guard: the process loop must include static analysis.

Regression for the F821 class of bug: `py_compile` and imports cannot see
undefined names inside lazily-evaluated annotations (`from __future__ import
annotations` + `-> "Fact"`). Two portable checks, no extra dependencies:

  1. pyflakes must pass on every package module (it catches F821, unused
     imports, unreachable code).
  2. every module's annotations must RESOLVE (typing.get_type_hints) — the
     exact check that would have caught the undefined `Fact`.
"""

import importlib
import os
import subprocess
import sys
import typing
from pathlib import Path

import openverifiers.legacy as openverifiers

PKG = Path(openverifiers.__file__).resolve().parent
PARENT = PKG.parents[1]
_SKIP_PARTS = ("tests", "examples", "experimental", "status", "docs",
               "openwiki", "plugin", "__pycache__")
MODULES: list[str] = []
for dirpath, dirnames, filenames in os.walk(PKG):
    dirnames[:] = [d for d in dirnames if d not in _SKIP_PARTS
                   and not d.startswith(".")]
    for fn in sorted(filenames):
        if not fn.endswith(".py"):
            continue
        rel = os.path.relpath(dirpath, PARENT).replace(os.sep, ".")
        dot = "" if fn == "__init__.py" else fn[:-3]
        fq = f"{rel}.{dot}" if dot else rel
        MODULES.append(fq)

def _module_paths():
    """resolve each allow-listed module to its exact file, so pyflakes does
    not directory-recurse into dirs the allow-list deliberately excludes"""
    files = []
    for fq in MODULES:
        try:
            spec = importlib.util.find_spec(fq)
        except (ImportError, ValueError):
            continue
        if spec and spec.origin and spec.origin.endswith(".py"):
            files.append(spec.origin)
    return files


def test_pyflakes_passes_on_all_package_modules():
    proc = subprocess.run([sys.executable, "-m", "ruff", "check", "--isolated",
                           "--select", "F", "--quiet", *_module_paths()],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        pytest_fail = "\n".join(proc.stdout.splitlines()[:20])
        assert False, f"pyflakes reported:\n{pytest_fail}"


def test_all_annotations_resolve():
    bad = []
    for fq in MODULES:
        try:
            mod = importlib.import_module(fq)
        except Exception as exc:  # import failure is itself a defect
            bad.append(f"{fq}: import failed {type(exc).__name__}: {exc}")
            continue
        for name, obj in vars(mod).items():
            if not callable(obj) or getattr(obj, "__module__", None) != fq:
                continue  # only names DEFINED here; imported/third-party
                          # symbols answer for their own annotations
            try:
                typing.get_type_hints(obj)
            except Exception as exc:
                bad.append(f"{fq}.{name}: unresolved annotation ({exc})")
    assert not bad, "unresolved annotations:\n" + "\n".join(bad[:20])