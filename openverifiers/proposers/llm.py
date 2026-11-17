"""LLM proposer adapter.

The model is any ``complete(prompt) -> str`` callable, so this module has no
SDK dependency and the kernel never sees a model. The prompt lists the facts,
requirements, the pack's transformations, and (on retries) the kernel's
structured failures; the reply must be a JSON proof ``{"steps": [...]}``.

``ScriptedModel`` replays fixed replies and records prompts; it stands in for
a real model in tests and the repair demo.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field

from openverifiers.kernel import (
    DomainPack,
    Fact,
    FormatError,
    Proof,
    Requirement,
    fact_to_dict,
    proof_from_dict,
    requirement_to_dict,
)

from .base import Feedback, ProposalError

Complete = Callable[[str], str]


def build_prompt(state: Sequence[Fact], requirements: Sequence[Requirement],
                 pack: DomainPack, feedback: Feedback | None) -> str:
    rules = [{"id": t.id, "tier": t.tier, "inputs": dict(t.inputs),
              "outputs": dict(t.outputs), "doc": t.doc}
             for t in pack.transformations.values()]
    parts = [
        "You propose proofs that a verification kernel will check step by step.",
        "Reply with only a JSON object {\"steps\": [{\"id\", \"transformation\", "
        "\"inputs\": {role: fact_id}, \"outputs\": {role: fact}}]}.",
        f"Domain: {pack.name}",
        "Facts:\n" + json.dumps([fact_to_dict(f) for f in state], indent=1),
        "Requirements:\n" + json.dumps([requirement_to_dict(r) for r in requirements], indent=1),
        "Transformations:\n" + json.dumps(rules, indent=1),
    ]
    if feedback is not None:
        parts.append(f"Attempt {feedback.attempt} was rejected. Kernel failures:\n"
                     + json.dumps([asdict(f) for f in feedback.failures], indent=1))
    return "\n\n".join(parts)


_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


def parse_reply(text: str) -> Proof:
    m = _FENCE.search(text)
    body = m.group(1) if m else text.strip()
    try:
        return proof_from_dict(json.loads(body))
    except (json.JSONDecodeError, FormatError) as exc:
        raise ProposalError(f"model reply is not a valid proof: {exc}") from exc


@dataclass
class LLMProposer:
    complete: Complete

    def propose(self, state: Sequence[Fact], requirements: Sequence[Requirement],
                domain_pack: DomainPack, feedback: Feedback | None = None) -> Proof:
        return parse_reply(self.complete(build_prompt(state, requirements, domain_pack,
                                                      feedback)))


@dataclass
class ScriptedModel:
    """A fake model: returns ``replies`` in order and keeps every prompt."""

    replies: list[str]
    prompts: list[str] = field(default_factory=list)

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self.prompts) > len(self.replies):
            raise ProposalError("scripted model has no more replies")
        return self.replies[len(self.prompts) - 1]
