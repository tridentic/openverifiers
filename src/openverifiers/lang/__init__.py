"""The OV front end: parser, name resolution, type and unit checking. See docs/LANGUAGE.md.

The names are loaded on first use (PEP 562): ``lang.check`` imports the object
layer, which imports ``lang.ast``, so importing ``check`` here would make
``import openverifiers.objects`` circular.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .check import Env, load
    from .errors import Diagnostic, OVError
    from .parser import parse

__all__ = ["Diagnostic", "Env", "OVError", "load", "parse"]
_WHERE = {"Env": "check", "load": "check", "Diagnostic": "errors", "OVError": "errors",
          "parse": "parser"}


def __getattr__(name: str) -> Any:
    if name in _WHERE:
        from importlib import import_module
        return getattr(import_module(f".{_WHERE[name]}", __name__), name)
    raise AttributeError(name)
