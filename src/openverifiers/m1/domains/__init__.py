"""Domain packs. Each module exposes ``PACK: DomainPack``.

Adding a pack means adding a module and a line here; the kernel never changes.
"""

from __future__ import annotations

import importlib

from openverifiers.m1.kernel import DomainPack

PACKS: dict[str, str] = {
    "math": "openverifiers.m1.domains.math",
    "code_requirements": "openverifiers.m1.domains.code_requirements",
}


def load(name: str) -> DomainPack:
    """Import and return the pack registered under ``name``."""
    if name not in PACKS:
        raise KeyError(f"unknown domain pack {name!r}; known: {sorted(PACKS)}")
    pack = importlib.import_module(PACKS[name]).PACK
    assert isinstance(pack, DomainPack)
    return pack
