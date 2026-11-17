"""OpenVerifiers domain bundle — every registered v2 Grammar.

`standard_grammars()` is the default merged set used by `submit()`; a caller
can pass an explicit list to restrict the whitelist.
"""

from __future__ import annotations

from ..v2 import Grammar
from .math import MATH
from .law import LAW
from .business import BUSINESS
from .english import ENGLISH

__all__ = ["MATH", "LAW", "BUSINESS", "ENGLISH", "standard_grammars"]

_ALL: tuple[Grammar, ...] = (MATH, LAW, BUSINESS, ENGLISH)


def standard_grammars() -> list[Grammar]:
    return list(_ALL)