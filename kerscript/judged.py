"""Judged steps — the typed model-backed transformation seam.

A judged step names a MODEL, an input schema, and an output schema. The
transformation the runtime sees is a normal registered Transformation; its
apply() delegates to the registered judge backend for that model. The
produced fact is stamped provenance="judged" — it is evidence-bearing and
typed, never deterministic truth, and never promoted to another tier by the
core.

Backend contract (v1): `fn(inputs: dict, params: dict) -> dict` returning
    {"verdict": str, "confidence": float, "evidence": [fact_id, ...]}
The verdict is checked against the declared output schema (enum options
when present). Deterministic stubs and LLM judges (Jev) plug into the same
registry; nothing in the core distinguishes them.
"""
from __future__ import annotations

import json
from typing import Callable

from openverifiers.facts import ActionFact, EnumValue
from openverifiers.model import Transformation, InputSpec

Judge = Callable[[dict, dict], dict]
_JUDGES: dict[str, Judge] = {}


def register_judge(name: str, fn: Judge) -> None:
    _JUDGES[name] = fn


def judges() -> list[str]:
    return sorted(_JUDGES)


class JudgeError(ValueError):
    pass


class JudgedTransformation(Transformation):
    """A registered transformation whose apply delegates to a judge backend.

    IR: judgements[]. schema maps output field -> {"type": "enum"|"number"|"bool", "options": [...]}.
    """

    def __init__(self, name: str, *, model: str,
                 inputs: tuple[InputSpec, ...], schema: dict[str, dict],
                 doc: str = ""):
        super().__init__(name, doc=doc, inputs=inputs)
        self.model = model
        self.schema = dict(schema)

    def apply(self, inputs: dict) -> ActionFact:
        if self.model not in _JUDGES:
            raise JudgeError(
                f"judged step {self.name!r} names model {self.model!r}, "
                f"which has no registered backend "
                f"(registered: {judges()})")
        try:
            raw = _JUDGES[self.model](inputs, {})
        except JudgeError:
            raise
        except Exception as exc:
            raise JudgeError(
                f"judge {self.model!r} raised {type(exc).__name__}: {exc}")
        verdict = raw.get("verdict")
        schema = self.schema.get("verdict", {"type": "enum"})
        if schema.get("type") == "enum":
            options = schema.get("options") or []
            if options and verdict not in options:
                raise JudgeError(
                    f"judge {self.model!r} returned verdict {verdict!r}, "
                    f"not in declared options {options}")
            value = EnumValue(enum=self.name, value=str(verdict))
        elif schema.get("type") == "number":
            value = raw.get("verdict")
        else:
            value = bool(raw.get("verdict"))
        details = {
            "model": self.model,
            "confidence": raw.get("confidence"),
            "evidence": list(raw.get("evidence") or ()),
        }
        return ActionFact(
            kind="judged", of=self.model, value=value,
            expr=json.dumps(details, sort_keys=True),
            provenance="judged",
            source=f"judged by {self.model} ({self.name})")


# ---------------------------------------------------------------------------
# deterministic stub judge — exercises the seam without an LLM
# ---------------------------------------------------------------------------
def _stub_english_agreement(inputs: dict, params: dict) -> dict:
    subj = inputs.get("subject")
    if subj is None:
        raise JudgeError("subject claim missing")
    of = getattr(subj, "of", None)
    ok = bool(of) and isinstance(of, str) and of.isalpha()
    return {"verdict": "consistent" if ok else "inconsistent",
            "confidence": 1.0,
            "evidence": [f.id for f in inputs.values()]}


register_judge("stub-english", _stub_english_agreement)