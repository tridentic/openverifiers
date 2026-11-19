"""Typed harness scene builder — the v2 frozen context IS a scene.

Adopts the pythonic-verifiers owner ergonomics (`with car as owner:` scoped
construction, typed `owner=` references) WITHOUT relaxing the security
model: everything here is harness-authoring code. The agent-facing trace
remains closed-registry; a scene is never handed to an agent wholesale.

A Scene produces the exact `dict[str, Fact]` shape `submit()` consumes —
after a structural validation pass that links labels to fact ids and owners
to frames by REFERENCE, not by string convention.

Frame-owned instants (the post's `with frame as owner: t = ...`) are bound
structurally via `ReferenceFrame.time` (the v1 mechanism) and additionally
exposed as facts so mission queries can reference them.
"""

from __future__ import annotations

from typing import Optional

from .facts import Fact
from .domains.physics import ReferenceFrame, PointObject, Time
from .domains.units_si import Second


class Scene:
    """One scenario's frozen, structurally-linked fact set.

    Usage (harness code only):

        s = Scene("chase_A")
        deer = s.object("deer")
        tiger = s.object("tiger")
        with deer:                                    # `with X as owner:`
            s.add(Position(value=..., unit=Meter(), frame=s.ground),
                  label="deer.start")                 # owner=deer auto-bound
        s.add(Quantity(value=300.0, unit=Meter(), id="run"), label="run")
        s.ground_time(0.0, label="ground.time")
        background = s.to_context()                   # validated dict
    """

    def __init__(self, name: str):
        self.name = name
        self.ground = ReferenceFrame(name=f"{name}.ground")
        self.objects: list[PointObject] = []
        self._facts: dict[str, Fact] = {}

    def object(self, stem: str) -> PointObject:
        """Create and register a scenario object bound to the scene frame."""
        obj = PointObject(name=f"{self.name}.{stem}", frame=self.ground)
        self.objects.append(obj)
        return obj

    def add(self, fact: Fact, label: Optional[str] = None) -> Fact:
        """Add a fact under `label` (defaults to the fact's own id). The
        label IS the identity: label != fact.id is a structural error, never
        a normalization."""
        label = label or fact.id
        if label != fact.id:
            raise ValueError(f"scene label {label!r} diverges from fact id "
                             f"{fact.id!r} — labels and ids must agree; no "
                             f"string alias convention")
        if label in self._facts:
            raise ValueError(f"duplicate scene fact {label!r}")
        self._facts[label] = fact
        return fact

    def ground_time(self, value: float, *, label: str = "ground.time") -> Time:
        """A frame-owned instant: bound to `ground.time` structALLY and
        exposed as a fact under `label` so queries can reference it."""
        if self.ground.time is not None:
            raise ValueError(f"scene {self.name!r} already declares a "
                             f"ground time")
        t = Time(value=value, unit=Second(), id=label)
        self.ground.time = t
        self.add(t, label=label)
        return t

    def validate(self) -> list[str]:
        """Structural consistency, by reference not convention:
          * label == fact id (enforced at add time, asserted again here)
          * every fact's frame, when present, is THE scene frame
          * every owned fact's owner is a registered scene object and its
            owner.frame agrees with the fact's own frame
        """
        problems: list[str] = []
        for label, f in self._facts.items():
            if f.id != label:
                problems.append(f"{label}: id {f.id!r}")
            frame = getattr(f, "frame", None)
            if frame is not None and frame is not self.ground:
                problems.append(f"{label}: frame {frame.name!r} is not the "
                                f"scene frame {self.ground.name!r}")
            owner = getattr(f, "owner", None)
            if owner is not None:
                if not any(owner is o for o in self.objects):
                    problems.append(f"{label}: owner "
                                    f"{getattr(owner, 'name', owner.id)!r} is "
                                    f"not a registered scene object")
                owner_frame = getattr(owner, "frame", None)
                if owner_frame is not None and frame is not None \
                        and owner_frame is not frame:
                    problems.append(
                        f"{label}: owner bound to {owner_frame.name!r}, fact "
                        f"frame {frame.name!r}")
        return problems

    def facts(self) -> dict[str, Fact]:
        problems = self.validate()
        if problems:
            raise ValueError(
                f"scene {self.name!r} failed structural validation:\n  "
                + "\n  ".join(problems))
        return dict(self._facts)

    def to_context(self) -> dict[str, Fact]:
        """submit()-compatible background: the validated fact dict."""
        return self.facts()