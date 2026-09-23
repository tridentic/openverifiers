"""OpenVerifiers — generic object base (ownership/context layer).

`PhysicalObject` is the polymorphic base every domain consumes; a future
subtype requires zero changes to `Quantity`, `EquationController`,
`ConditionController`, or the query machinery, because core classes only
ever reference this base. Concrete subtypes (e.g. physics `PointObject`)
live in their domain packages."""

from __future__ import annotations

import contextvars
from typing import Optional

from pydantic import BaseModel, ConfigDict

# active `with <object> as owner:` construction context — context-local, not
# a mutable global; nested and concurrent scenes each see their own value.
_ACTIVE_OWNER: "contextvars.ContextVar[Optional[PhysicalObject]]" = \
    contextvars.ContextVar("verifier_active_owner", default=None)


def active_owner() -> Optional["PhysicalObject"]:
    """The owner the current construction block was entered with, if any."""
    return _ACTIVE_OWNER.get()


class PhysicalObject(BaseModel):
    """Anything a fact can belong to. Domain code must depend on this base."""

    model_config = ConfigDict(frozen=True)

    id: str

    def model_post_init(self, __context) -> None:
        from .context import note
        note(self)

    # -- `with <object> as owner:` harness ergonomics (post: pythonic
    #    verifiers) — construction inside the block adopts this object as its
    #    typed owner. Purely scoping: the agent-facing trace never sees this.
    def __enter__(self) -> "PhysicalObject":
        self._previous_owner = _ACTIVE_OWNER.get()
        _ACTIVE_OWNER.set(self)
        return self

    def __exit__(self, *_exc) -> None:
        _ACTIVE_OWNER.set(getattr(self, "_previous_owner", None))