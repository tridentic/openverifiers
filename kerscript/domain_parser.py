"""KDScript-Domain parser: text -> DomainIR (pure data).

v1 grammar (line-oriented, `#` comments, INDENTATION scopes):

    domain <name>                        # required, first statement
    doc <free text>
    namespace <name>                     # nested blocks; children indent
        ... declarations ...             # names resolve RELATIVE to scope

    type <name> = <base>                 # base: fact | quantity | action
    type <name> extends <base> [unit(<token>)]    # quantity subtype
    type <name> extends <base> [kind(<str>)]      # action subtype
    unit <token>, <token>
    fact <id>: quantity(<value>, <unit>)
    fact <id>: action(<kind>, <value>) [of=<x>]
    relation <name>: <expr> unit(<k>=<unit-or-type>,...) out(<v>) [param(<p>,...)]
    transform <name>: builtin(<b>) [param(<p>,...)] [input(<r>:<type>,...)]
                 [guard(<g>,...)] [doc(<text>)]
    transform <name>: relation(<rel>) [guard(<g>,...)]
    judge <name>: model(<m>) input(<r>:<type>,...) schema(<f>=<type>[|<opt>],...)
    exclusive(<a>, <b>, ...)

Nesting: a declaration inside `namespace foo` gets the `foo.` prefix; inside
`foo bar` (nested) `foo.bar.`. Names with explicit dots are kept as written.
Type references inside a scope resolve to the nearest enclosing declaration,
then the bare name.

Guard grammar: same_owner(a,b) | frame_eq(a,b) | kind(r, quantity|action)
                | unit(r, token) | positive(r)

Expressions are sympy-compatible strings; `=` separates the two sides; `**`
is power; `sqrt(...)`, `pi` available. The separator keywords `unit(` /
`out(` appear at top level only.
"""
from __future__ import annotations

import re
from typing import Optional

from . import ir as _ir
from .units import _TABLE as UNIT_TABLE, derive_unit

_FACT_RE = re.compile(
    r"^fact\s+(\S+):\s*(quantity|action)\(([^)]*)\)(.*)$")
_TYPE_ALIAS_RE = re.compile(r"^type\s+(\S+)\s*=\s*(\w+)\s*$")
_TYPE_EXT_RE = re.compile(
    r"^type\s+(\S+)\s+extends\s+(\w+)(.*)$")
_TYPE_KV = re.compile(r"^\s*(unit|kind)\(([^)]*)\)\s*$")
_KV_TAIL = re.compile(r"^\s*(\w+)\s*=\s*([^\s]+)\s*(.*)$")

_BASES = {"fact", "quantity", "action", "entity"}

_TYPE_BASE_FIELDS = {"quantity": ("unit",), "action": ("kind",),
                     "entity": (), "fact": ()}


def _split_groups(text: str) -> list[tuple[str, str]]:
    """Top-level key(...) groups; nested parens (sqrt(x)) stay inside."""
    out: list[tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "(":
            i += 1
            continue
        j = i - 1
        while j >= 0 and (text[j].isalnum() or text[j] == "_"):
            j -= 1
        key = text[j + 1:i].strip()
        depth, k = 1, i + 1
        while k < n and depth:
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
            k += 1
        out.append((key, text[i + 1:k - 1].strip()))
        i = k
    return out


def _tail_kv(rest: str) -> dict:
    kv: dict[str, str] = {}
    m = _KV_TAIL.match(rest)
    if m:
        kv[m.group(1)] = m.group(2).strip("\"'")
    return kv


def _csv(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


class _Scope:
    """Indentation scope tracker + name resolution."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.path: list[str] = []
        self.levels: list[int] = []

    def qualify(self, name: str) -> str:
        if "." in name:
            return name                     # author chose the full name
        return ".".join(self.path + [name]) if self.path else name

    def resolve_type(self, name: str) -> Optional[str]:
        types = self.doc.get("types", {})
        if name in types:
            return name
        for i in range(len(self.path), 0, -1):
            key = ".".join(self.path[:i] + [name])
            if key in types:
                return key
        return None

    def enter(self, name: str, indent: int) -> None:
        self.path.append(name)
        self.levels.append(indent)

    def settle(self, indent: int) -> None:
        while self.levels and indent < self.levels[-1]:
            self.path.pop()
            self.levels.pop()


def parse_domain(text: str) -> dict:
    doc: dict | None = None
    scope: _Scope | None = None
    for raw in text.splitlines():
        content = raw.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip())
        line = content.strip()
        if line.startswith("domain "):
            if doc is not None:
                raise ValueError("duplicate `domain` declaration")
            name = line.split(None, 1)[1].strip()
            doc = _ir.new_domain(name)
            doc["types"] = {}
            scope = _Scope(doc)
            continue
        if doc is None:
            raise ValueError(f"declaration before `domain` line: {line!r}")
        if scope is None:
            continue
        if line.startswith("namespace "):
            scope.settle(indent)
            scope.enter(line.split(None, 1)[1].strip(), indent)
            continue
        scope.settle(indent)
        _parse_line(doc, scope, line)
    if doc is None:
        raise ValueError("KDScript-Domain document has no `domain` line")
    return doc


def _parse_line(doc: dict, scope: _Scope, line: str) -> None:
    if line.startswith("doc "):
        doc["doc"] = (doc["doc"] + " " if doc["doc"] else "") + \
            line[4:].strip()
        return

    if line.startswith("type "):
        m = _TYPE_ALIAS_RE.match(line)
        if m and m.group(2) in _BASES:
            doc["types"][scope.qualify(m.group(1))] = {
                "base": m.group(2), "unit": None, "kind": None,
                "framed": False, "parent": None}
            return
        m = _TYPE_EXT_RE.match(line)
        if not m:
            raise ValueError(f"cannot parse type line: {line!r}")
        tname, base = m.group(1), m.group(2)
        parent = None
        if base in _BASES:
            eff_base = base
        else:
            parent = scope.resolve_type(base)
            if parent is None:
                raise ValueError(
                    f"type {tname}: unknown base {base!r}")
            eff_base = doc["types"][parent]["base"]
        rest = m.group(3).strip()
        unit = kind = None
        framed = False
        for m2 in re.finditer(r"(unit|kind)\s*\(([^)]*)\)|\bframed\b", rest):
            if m2.group(1) == "unit":
                unit = m2.group(2).strip()
            elif m2.group(1) == "kind":
                kind = m2.group(2).strip()
            else:
                framed = True
        if _TYPE_BASE_FIELDS[eff_base] == ("unit",) and unit is None:
            raise ValueError(f"type {tname}: quantity subtype needs unit(...)")
        if _TYPE_BASE_FIELDS[eff_base] == ("kind",) and kind is None:
            raise ValueError(f"type {tname}: action subtype needs kind(...)")
        if eff_base == "entity" and (unit or kind):
            raise ValueError(f"type {tname}: entity subtype cannot carry "
                             f"unit()/kind()")
        rec = {"base": eff_base, "unit": unit, "kind": kind,
               "framed": framed, "parent": parent}
        if parent is not None:
            rec["unit"] = rec["unit"] or doc["types"][parent].get("unit")
            rec["kind"] = rec["kind"] or doc["types"][parent].get("kind")
            rec["framed"] = (rec["framed"]
                             or doc["types"][parent].get("framed", False))
        doc["types"][scope.qualify(tname)] = rec
        return

    if line.startswith("unit "):
        body = line[5:].strip()
        if "=" in body:
            name, _, expr = body.partition("=")
            name = name.strip()
            if not re.match(r"^[A-Za-z_][\w]*$", name):
                raise ValueError(f"unit name {name!r} is not an identifier")
            fields, scale = derive_unit(name, expr.strip())
            if name in UNIT_TABLE:
                raise ValueError(f"unit {name!r} redefines a built-in token")
            doc["units"][name] = {"dimension": dict(fields), "scale": scale}
            return
        for tok in _csv(body):
            if tok not in UNIT_TABLE:
                raise ValueError(f"unit {tok!r} is not in the unit table")
            fields, scale = UNIT_TABLE[tok]
            doc["units"][tok] = {"dimension": dict(fields), "scale": scale}
        return

    if line.startswith("object "):
        m = re.match(r"^object\s+(\S+)\s*:\s*(\S+)(.*)$", line)
        if not m:
            raise ValueError(f"cannot parse object line: {line!r}")
        oname, otype, rest = m.groups()
        groups = dict(_split_groups(rest))
        if scope.resolve_type(otype) is None:
            raise ValueError(
                f"object {oname}: unknown type {otype!r}")
        doc["objects"].append({"id": scope.qualify(oname),
                               "type": scope.resolve_type(otype),
                               "frame": groups.get("frame")})
        return

    if line.startswith("fact "):
        m = _FACT_RE.match(line)
        if not m:
            raise ValueError(f"cannot parse fact line: {line!r}")
        fid, kind, inner, rest = m.groups()
        kv = _tail_kv(rest)
        groups = dict(_split_groups(" " + (rest or "")))
        owner = groups.get("owner")
        frame = groups.get("frame")
        fid = scope.qualify(fid)
        if kind == "quantity":
            args = _csv(inner)
            if len(args) != 2:
                raise ValueError(
                    f"quantity fact needs (value, unit): {line!r}")
            doc["facts"].append({"id": fid, "kind": "quantity",
                                 "value": float(args[0]), "unit": args[1],
                                 "of": None, "owner": owner, "frame": frame,
                                 "source": kv.get("source", "")})
        else:
            args = _csv(inner)
            if len(args) != 2:
                raise ValueError(
                    f"action fact needs (kind, value): {line!r}")
            doc["facts"].append({"id": fid, "kind": "action",
                                 "value": args[1], "of": kv.get("of"),
                                 "kind_name": args[0],
                                 "owner": owner, "frame": frame,
                                 "source": kv.get("source", "")})
        return

    if line.startswith("relation "):
        m = re.match(r"^relation\s+(\S+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"cannot parse relation line: {line!r}")
        local, rest = m.groups()
        groups = dict(_split_groups(rest))
        unit_g = groups.get("unit")
        out_g = groups.get("out")
        if unit_g is None or out_g is None:
            raise ValueError(f"relation needs unit(...) and out(...): {line!r}")
        expr = rest[:rest.index(" unit(")].strip()
        units: dict[str, str] = {}
        types: dict[str, str] = {}
        for item in (t.strip() for t in unit_g.split(",")):
            if not item:
                continue
            var, _, ref = item.partition("=")
            var = var.strip()
            tiref = scope.resolve_type(ref.strip())
            if tiref is not None:
                t = doc["types"][tiref]
                tok = t["unit"] or "dimless"
                types[var] = tiref
            elif ref.strip() in UNIT_TABLE:
                tok = ref.strip()
            else:
                raise ValueError(
                    f"relation {local}: {ref!r} is neither a type nor a unit")
            if tok not in UNIT_TABLE:
                raise ValueError(f"relation {local}: unknown unit {tok!r}")
            units[var] = tok
        out_var = out_g.strip()
        if out_var not in units:
            raise ValueError(
                f"relation {local}: out({out_var}) is not a declared variable")
        rec = {"name": scope.qualify(local), "expr": expr,
               "units": units, "types": types, "out": out_var,
               "param": _csv(groups.get("param", "")), "doc": ""}
        doc["relations"].append(rec)
        return

    if line.startswith("transform "):
        m = re.match(r"^transform\s+(\S+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"cannot parse transform line: {line!r}")
        local, rest = m.groups()
        groups = dict(_split_groups(rest))
        if "builtin" in groups and "relation" in groups:
            raise ValueError(f"transform {local} cannot use both builtin() "
                             f"and relation()")
        if "builtin" not in groups and "relation" not in groups:
            raise ValueError(f"transform {local} needs builtin(<name>) or "
                             f"relation(<name>)")
        rec = {"name": scope.qualify(local),
               "builtin": groups.get("builtin"),
               "relation": groups.get("relation"),
               "param": _csv(groups.get("param", "")),
               "input": _typed_csv(groups.get("input", "")),
               "guard": [_guard(t) for t in _csv(groups.get("guard", ""))],
               "doc": groups.get("doc", "")}
        doc["transforms"].append(rec)
        return

    if line.startswith("judge "):
        m = re.match(r"^judge\s+(\S+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"cannot parse judge line: {line!r}")
        local, rest = m.groups()
        groups = dict(_split_groups(rest))
        if "model" not in groups or "input" not in groups:
            raise ValueError(f"judge {local} needs model(<m>) and input(...)")
        inputs = []
        for item in _typed_csv(groups["input"]):
            inputs.append({"role": item["role"], "type": item["type"]})
        schema = {}
        for item in _csv(groups.get("schema", "verdict=enum")):
            field, _, spec = item.partition("=")
            parts = spec.split("|")
            schema[field.strip()] = {"type": parts[0].strip(),
                                     "options": [p.strip() for p in parts[1:]]
                                     or None}
        doc["judgements"].append({"name": scope.qualify(local),
                                  "model": groups["model"],
                                  "input": inputs, "schema": schema,
                                  "doc": groups.get("doc", "")})
        return

    if line.startswith("exclusive"):
        m = re.match(r"^exclusive\(([^)]*)\)\s*$", line)
        if not m:
            raise ValueError(f"cannot parse exclusive line: {line!r}")
        doc["exclusive"].append([t.strip() for t in m.group(1).split(",")
                                 if t.strip()])
        return

    raise ValueError(f"unrecognized KDScript-Domain line: {line!r}")


def _typed_csv(text: str) -> list[dict]:
    items = []
    for part in _csv(text):
        role, _, t = part.partition(":")
        if not t:
            role, _, t = part.partition("=")     # legacy `role=kind` form
        items.append({"role": role.strip(), "type": t.strip()})
    return items


_GUARD_ARITY = {"same_owner": 2, "frame_eq": 2, "kind": 2, "unit": 2,
                "positive": 1}


def _guard(text: str) -> dict:
    m = re.match(r"^(\w+)\(([^)]*)\)$", text.strip())
    if not m:
        raise ValueError(f"cannot parse guard {text!r}")
    op, inner = m.groups()
    args = _csv(inner)
    if len(args) != _GUARD_ARITY.get(op, -1):
        raise ValueError(f"guard {op} takes {_GUARD_ARITY.get(op)} "
                         f"argument(s), got {len(args)}: {text!r}")
    return {"op": op, "args": args}


def _typed_csv_deprecated(text: str) -> list[str]:
    return _csv(text)


def load_domain(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return parse_domain(fh.read())