"""The OpenVerifiers Python SDK (v1): a small, stable surface over the `ov` runtime.

    from openverifiers import sdk
    report = sdk.check("examples/chem/q11.ov")
    for q in report.queries:
        print(q.verdict, q.query, q.values, q.trust)

Everything in ``__all__`` is the public API. Within v1 its names, parameters and
result fields only grow; nothing is renamed or removed (``SDK_VERSION``). The SDK
is untrusted glue: every verdict it returns is the kernel's (or, for object
queries, the trusted checker's), exactly as `ov run` prints it. See docs/SDK.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import gate as _gate
from . import mcp_gate as _mcp
from . import paper as _paper
from .bench.run import outcome as _outcome
from .lang.errors import Diagnostic, OVError
from .objects.engine import Settings
from .runner import FileResult
from .runner import run_file as _run_file
from .state.export import export as _export

__all__ = [
    "SDK_VERSION",
    "ClassCheck",
    "Diagnostic",
    "OVError",
    "QueryResult",
    "Report",
    "blueprints",
    "check",
    "check_source",
    "export_state",
    "gate_files",
    "gate_tool_call",
]

#: The SDK surface version: 1.x keeps every public name and field of 1.0.
SDK_VERSION = "1.0"


@dataclass(frozen=True)
class QueryResult:
    """One query's answer. ``verdict`` is PROVEN, REFUTED, UNKNOWN or INCONSISTENT;
    ``trust`` names what it rests on (``kernel``: the independent checker accepted it;
    anything else, such as ``z3_unsat``, is a solver result that ``--strict`` refuses)."""

    query: str
    line: int
    verdict: str
    trust: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    reason: str = ""
    missing: tuple[str, ...] = ()

    @property
    def proven(self) -> bool:
        return self.verdict == "PROVEN"

    @property
    def kernel_checked(self) -> bool:
        """True when the verdict rests on the trusted checker alone."""
        return self.verdict != "UNKNOWN" and set(self.trust) == {"kernel"}


@dataclass(frozen=True)
class ClassCheck:
    """A class consistency check or a class theorem."""

    check: str
    verdict: str
    trust: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class Report:
    """The result of checking one OV file."""

    file: str
    queries: tuple[QueryResult, ...]
    classes: tuple[ClassCheck, ...]
    provisional: tuple[str, ...] = ()       # draft packages loaded: results are provisional
    failed_expectations: int = 0
    raw: FileResult | None = field(default=None, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        """Every `expect` holds and no theorem is refuted or class empty (like `ov check`)."""
        return self.failed_expectations == 0 and not any(
            c.verdict in ("REFUTED", "INCONSISTENT") for c in self.classes)

    def to_json(self) -> dict[str, Any]:
        """Plain data (lists and strings), stable within v1, for agents."""
        return {"file": self.file, "ok": self.ok, "provisional": list(self.provisional),
                "failed_expectations": self.failed_expectations,
                "queries": [asdict(q) for q in self.queries],
                "classes": [asdict(c) for c in self.classes]}


def _settings(strict: bool, drafts: bool) -> Settings:
    return Settings(strict=strict, drafts=drafts and not strict)


def _report(path: Path, res: FileResult) -> Report:
    out = _outcome(res)
    qs = tuple(QueryResult(q["query"], q["line"], q["verdict"], tuple(q.get("trust", [])),
                           tuple(q.get("values", [])), tuple(q.get("assumptions", [])),
                           q.get("reason", ""), tuple(q.get("missing", [])))
               for q in out["queries"])
    cs = tuple(ClassCheck(c["check"], c["verdict"], tuple(c["trust"]), c["reason"] or "")
               for c in out["classes"])
    return Report(str(path), qs, cs, tuple(res.draft_packages), len(res.failed), res)


def check(path: str | Path, *, strict: bool = False, drafts: bool = False) -> Report:
    """Check an OV file, as `ov check` does: run every query, expectation and class
    check. ``strict``: only kernel-checked verdicts count (solver results become
    UNKNOWN; drafts never load). ``drafts``: also load unapproved packages from
    drafts/ (results are then provisional). Raises OVError if the file does not load."""
    p = Path(path)
    return _report(p, _run_file(p, files={str(p)}, settings=_settings(strict, drafts)))


def check_source(source: str, *, name: str = "inline.ov", directory: str | Path = ".",
                 strict: bool = False, drafts: bool = False) -> Report:
    """Check OV source text. ``directory`` is where imports of local files resolve;
    nothing is written to disk."""
    p = Path(directory) / name
    return _report(p, _run_file(p, source=source, files={str(p)},
                                settings=_settings(strict, drafts)))


def export_state(path: str | Path, scenario: str | None = None) -> dict[str, object]:
    """The OVState of a scenario (canonical JSON with its SHA-256), as `ov state` writes
    it. Import it in OV with ``import state "file.json" as name``."""
    return _export(Path(path), scenario)


def gate_tool_call(policy: str | Path, tool: str, target: str, *,
                   drafts: bool = False) -> dict[str, Any]:
    """The agent tool-call gate: ``{"decision": "permitted" | "refused" | "needs_human" |
    "unknown", ...}`` for one requested call under an OV policy file. A tool or target
    the policy does not name goes to a human."""
    return _mcp.decide(Path(policy), tool, target, drafts)


def gate_files(paths: Iterable[str | Path], *, drafts: bool = False
               ) -> list[tuple[str, bool, str]]:
    """`ov gate` on these OV files: (path, ok, one line) each."""
    return [(str(p), *_gate.check_file(Path(p), drafts)) for p in paths]


def blueprints(path: str | Path, *, drafts: bool = False) -> list[dict[str, Any]]:
    """OV-Paper blueprints (plain JSON) for every class theorem in the file."""
    p = Path(path)
    return _paper.blueprints(_run_file(p, files={str(p)}, settings=_settings(False, drafts)))


_ = (Diagnostic, OVError)                    # re-exported for callers that catch them
