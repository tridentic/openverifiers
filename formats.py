"""OpenVerifiers — file I/O (audit only).

`.ovpv` is a JSON audit trace WRITTEN BY THE ENGINE AFTER A RUN. It is never
hand-authored and never parsed back as input — the verification surface is
Python (`EquationController.solve_for`, `ConditionController.check`).
"""

from __future__ import annotations

import json
import os


def build_audit(result, *, source: str = "python") -> dict:
    """Project a VerificationResult into the .ovpv audit JSON shape."""
    return {
        "format": "ovpv",
        "version": "0.3",
        "source": source,
        "result": "pass" if result.status == "RESOLVED" else "fail",
        "status": result.status,
        "target": result.target,
        "answer": None if result.answer is None else str(result.answer),
        "trace": result.trace,
    }


def save_audit(path: str, result, *, source: str = "python") -> dict:
    """Write the audit trace to `path` (.ovpv JSON)."""
    audit = build_audit(result, source=source)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(audit, fh, indent=2)
    return audit