"""OV diagnostics: a stable code, a message, the span, and a one-line fix hint.

Codes (docs/LANGUAGE.md lists every one):

* ``E1xx`` syntax: E101 unexpected token, E102 unexpected character,
  E103 unknown unit, E104 bad number.
* ``E2xx`` names and modules: E201 unknown name, E202 duplicate declaration,
  E203 package not found, E204 unknown field, E205 wrong number of arguments,
  E206 not allowed here, E207 unsupported until a later milestone.
* ``E3xx`` types and units: E301 dimension mismatch, E302 type mismatch,
  E303 not a quantity.
* ``E4xx`` lowering: E401 nothing to solve for, E402 cannot solve,
  E403 unsafe variable, E404 generator source not finite.
* ``W2xx`` warnings: W201 undeclared type used as an opaque entity type,
  W202 a theorem may be vacuous (``exists`` over an invariant's generator).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..raw.program import Span


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    span: Span
    hint: str = ""

    @property
    def warning(self) -> bool:
        return self.code.startswith("W")

    def render(self, source: str | None = None) -> str:
        sp = self.span
        kind = "warning" if self.warning else "error"
        out = [f"{sp.file}:{sp.line}:{sp.col}: {kind}[{self.code}]: {self.message}"]
        if source is not None:
            lines = source.splitlines()
            if 0 < sp.line <= len(lines):
                text = lines[sp.line - 1]
                width = (sp.end_col - sp.col) if sp.end_line == sp.line else len(text) - sp.col + 1
                out.append(f"  {text}")
                out.append("  " + " " * (sp.col - 1) + "^" * max(1, width))
        if self.hint:
            out.append(f"  hint: {self.hint}")
        return "\n".join(out)


class OVError(Exception):
    """One or more errors. ``diagnostics`` may also hold warnings."""

    def __init__(self, diagnostics: list[Diagnostic], sources: dict[str, str] | None = None
                 ) -> None:
        self.diagnostics = diagnostics
        self.sources = sources or {}
        super().__init__(self.render())

    @property
    def codes(self) -> list[str]:
        return [d.code for d in self.diagnostics if not d.warning]

    def render(self) -> str:
        return "\n".join(d.render(self.sources.get(d.span.file)) for d in self.diagnostics)
