"""KDScript-Domain parser: text -> DomainIR (pure data).

Curly-brace block syntax — Pythonic/C# type-hint hybrid: explicit `{ }`
scoping, typed fields with `:` annotations. One declaration per statement;
blocks may open inline (`entity X { }`) or across lines.

    domain <name> {
        doc <free text>
        unit <token>, <token>                         # built-in reference
        unit <name> = base(<dim>) | <expr>            # derivation

        # -- entities: nominal object classes (is-a) -----------------------
        entity <Name>
        entity <Name> extends <Parent>
        object <id>: <EntityType>

        # -- struct types: typed fields ------------------------------------
        type <Name> {
            owner: <EntityType>       # fact belongs to an object of this type
            frame: <EntityType>       # fact carries a reference frame
            value: quantity<Unit>     # quantity structs (unit-aware)
            kind: <str>               # action structs only
        }

        # -- fact instances (frozen context) --------------------------------
        fact <id>: <Type> {
            owner: <object-id>
            frame: <object-id>
            value: <scalar>
        }

        # -- relations -------------------------------------------------------
        relation <name> {
            inputs: { <var>: <Struct>, ... }          # typed, any direction
            equation: <lhs> == <rhs>                  # sympy-compatible
            out: <var> | <var>: <Struct>
            param: [<p>, ...]                         # step-bound variables
            guard: [<guard>(...), ...]                # declarative conditions
        }

        # -- transforms -------------------------------------------------------
        transform <name> {
            builtin: <builtin>                        # or relation: <rel>
            param: [<p>, ...]
            input: [<role>: <Struct>, ...]
            guard: [<guard>(...), ...]
        }

        # -- judged steps ------------------------------------------------------
        judge <name> {
            model: <backend>
            input: [<role>: <Struct>, ...]
            schema: <field>: <type>[|<opt>, ...]
        }

        exclusive: (<a>, <b>, ...)
    }

GUARDS (engine-evaluated, declarative):
  same_owner(a,b) | different_owner(a,b) | frame_eq(a,b) |
  kind(r, quantity|action) | unit(r, token) | framed(r) |
  positive(r)   [] = comma-separated
"""
from __future__ import annotations

import re

from . import ir as _ir
from .units import _TABLE as UNIT_TABLE, derive_unit

_BLOCK_KINDS = {"domain", "entity", "fact", "relation", "transform", "judge"}
_FIELD_RE = re.compile(r"^\s*(\w+)\s*:\s*(.*?)\s*$")
_INPUTS_RE = re.compile(r"^\s*\{\s*(.*?)\s*\}\s*$")
_LISTS = ("param", "input", "guard")


def parse_domain(text: str) -> dict:
    doc: dict | None = None
    stack: list[tuple[str, str]] = []      # (kind, name)
    for raw in text.splitlines():
        content = raw.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        line = content.strip()
        # single-line block: `entity X { }`, `fact n { unit: x }`
        m = re.match(r"^(\S.*?)\{\s*(.*)\}\s*$", line)
        if m and m.group(1).strip().split(None, 1)[0] in \
                ("domain", "entity", "type", "fact", "relation",
                 "transform", "judge"):
            head, inner = m.group(1).strip(), m.group(2)
            ndoc = _open_block(doc, stack, head)
            if ndoc is not None:
                doc = ndoc
            if inner.strip():
                _field_lines(doc, stack, inner)
            _close_block(doc, stack)
            continue
        if line.endswith("{"):
            head = line[:-1].strip()
            ndoc = _open_block(doc, stack, head)
            if ndoc is not None:
                doc = ndoc
            continue
        if line == "}":
            _close_block(doc, stack)
            continue
        # object instances are domain-level statements
        if line.startswith("object ") and len(stack) == 1 \
                and stack[0][0] == "domain":
            _object_line(doc, line)
            continue
        m = _FIELD_RE.match(line)
        if m:
            block = stack[-1] if stack else ("domain", "")
            _field(block, m.group(1), m.group(2), doc)
            continue
        raise ValueError(f"cannot parse line: {line!r}")
    if stack:
        raise ValueError(f"unclosed block(s): {stack}")
    if doc is None:
        raise ValueError("KDScript-Domain document has no `domain` block")
    return doc


def _field_lines(doc, stack, text: str) -> None:
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        m = _FIELD_RE.match(part)
        if not m:
            raise ValueError(f"cannot parse inline field: {part!r}")
        block = stack[-1] if stack else ("domain", "")
        _field(block, m.group(1), m.group(2), doc)


def _close_block(doc, stack) -> None:
    if not stack:
        raise ValueError("unbalanced '}'")
    stack.pop()


def _object_line(doc, line) -> None:
    m = re.match(r"^object\s+(\S+)\s*:\s*(\S+)\s*$", line)
    if not m:
        raise ValueError(f"cannot parse object line: {line!r}")
    if m.group(2) not in doc["types"]:
        raise ValueError(f"object {m.group(1)}: unknown type {m.group(2)!r}")
    doc["objects"].append({"id": m.group(1), "type": m.group(2)})


def _open_block(doc, stack, head: str):
    """Open a block; for the `domain` root this CREATES and returns the IR
    document, for all other blocks it mutates in place."""
    parts = head.split()
    if not parts:
        return doc
    kind = parts[0]
    if kind == "domain":
        if doc is not None:
            raise ValueError("duplicate `domain` block")
        if len(parts) != 2:
            raise ValueError("domain needs a name")
        ndoc = _ir.new_domain(parts[1])
        ndoc["types"] = {}
        ndoc["units"] = {}
        stack.append(("domain", parts[1]))
        return ndoc
    if doc is None:
        raise ValueError(f"declaration before `domain` block: {head!r}")
    if kind == "entity":
        if len(parts) == 2:
            tname, chain = parts[1], None
        elif len(parts) == 4 and parts[2] == "extends":
            tname, chain = parts[1], parts[3]
        else:
            raise ValueError(f"entity syntax: entity NAME [extends P]: "
                             f"{head!r}")
        if chain is not None and chain not in doc["types"] and \
                chain != "entity":
            raise ValueError(f"entity {tname}: unknown parent {chain!r}")
        doc["types"][tname if "." not in tname else tname] = {
            "base": "entity", "unit": None, "kind": None, "framed": False,
            "parent": chain or "entity", "fields": {}}
        stack.append(("entity", tname))
        return
    if kind == "type":
        if len(parts) != 2:
            raise ValueError(f"type needs a name: {head!r}")
        if parts[1] in doc["types"]:
            raise ValueError(f"duplicate type {parts[1]!r}")
        doc["types"][parts[1]] = {"base": "fact", "unit": None,
                                  "kind": None, "framed": False,
                                  "parent": None, "fields": {}}
        stack.append(("type-schema", parts[1]))
        return
    if kind == "fact":
        # fact <id>: <Type> { ... } — a typed INSTANCE (assertion)
        if len(parts) == 3 and parts[1].endswith(":"):
            fid, tname = parts[1][:-1], parts[2]
            if tname not in doc["types"]:
                raise ValueError(
                    f"fact {fid}: unknown struct type {tname!r}")
            doc.setdefault("facts", []).append(
                {"id": fid, "type": tname, "fields": {}})
            stack.append(("fact-inst", (fid, tname)))
            return
        raise ValueError(f"fact syntax: fact <id>: <Type> {{ }}: {head!r}")
    if kind == "relation":
        if len(parts) != 2:
            raise ValueError(f"relation needs a name: {head!r}")
        stack.append(("relation", parts[1]))
        return
    if kind == "transform":
        if len(parts) != 2:
            raise ValueError(f"transform needs a name: {head!r}")
        stack.append(("transform", parts[1]))
        return
    if kind == "judge":
        if len(parts) != 2:
            raise ValueError(f"judge needs a name: {head!r}")
        stack.append(("judge", parts[1]))
        return
    raise ValueError(f"unknown block kind {kind!r}")


def _field(block, key: str, val: str, doc: dict) -> None:
    kind, name = block
    if kind == "domain":
        if key == "unit":
            _unit_line(doc, val)
        elif key == "exclusive":
            doc["exclusive"].append(
                [t.strip() for t in val.strip("()").split(",")
                 if t.strip()])
        elif key == "doc":
            doc["doc"] = (doc["doc"] + " " if doc["doc"] else "") + val
        return
    if kind == "type-schema":
        rec = doc["types"][name]
        if key in ("owner", "frame", "value", "kind"):
            rec["fields"][key] = {"type": val}
            if key == "kind":
                rec["kind"] = val.strip()
            if key == "owner":
                rec["owner"] = val.strip()
            if key == "frame":
                rec["frame"] = val.strip()
            if key == "value" and val.strip().startswith("quantity<"):
                rec["unit"] = _unit_of_quantity(val)
        else:
            raise ValueError(f"type {name}: unknown field {key!r}")
        return
    if kind == "fact-inst":
        fid, tname = name
        inst = next((i for i in doc.get("facts", [])
                     if i["id"] == fid and i.get("type") == tname), None)
        if inst is None:
            raise ValueError(f"internal: instance {fid} not registered")
        if key in ("owner", "frame", "value", "kind"):
            inst["fields"][key] = val.strip()
        else:
            raise ValueError(f"fact {fid}: unknown instance field {key!r}")
        return
    if kind == "relation" and key in ("inputs", "equation", "out", "param",
                                      "guard", "doc"):
        _relation_field(name, doc, key, val)
        return
    if kind == "transform" and key in ("builtin", "relation", "param",
                                       "input", "guard", "doc"):
        _transform_field(name, doc, key, val)
        return
    if kind == "judge" and key in ("model", "input", "schema", "doc"):
        _judge_field(name, doc, key, val)
        return
    raise ValueError(f"block {kind} {name}: unknown field {key!r}")


def _relation_field(name, doc, key, val) -> None:
    rec = next((r for r in doc["relations"] if r["name"] == name), None)
    if rec is None:
        rec = {"name": name, "expr": "", "units": {}, "types": {},
               "out": "", "out_type": None, "param": [], "guards": [],
               "doc": ""}
        doc["relations"].append(rec)
    if key == "inputs":
        m = _INPUTS_RE.match(val)
        if not m:
            raise ValueError(f"relation {name}: inputs must be "
                             f"{{ var: Type, ... }}")
        for item in (t.strip() for t in m.group(1).split(",")):
            if not item:
                continue
            var, _, t = item.partition(":")
            var, t = var.strip(), t.strip()
            rec["types"][var] = t
        return
    if key == "equation":
        rec["expr"] = val
        return
    if key == "out":
        parts = [p.strip() for p in val.split(":")]
        rec["out"] = parts[0]
        if len(parts) > 1:
            rec["out_type"] = parts[1]
        return
    if key == "param":
        rec["param"] = _csv(val.strip().strip("[]"))
        return
    if key == "guard":
        rec["guards"] = [_guard(t) for t in _csvp(val.strip().strip("[]"))]
        return
    rec["doc"] = val


def _transform_field(name, doc, key, val) -> None:
    rec = next((r for r in doc["transforms"] if r["name"] == name), None)
    if rec is None:
        rec = {"name": name, "builtin": None, "relation": None, "param": [],
               "input": [], "guards": [], "doc": ""}
        doc["transforms"].append(rec)
    if key == "builtin":
        rec["builtin"] = val.strip()
    elif key == "relation":
        rec["relation"] = val.strip()
    elif key == "param":
        rec["param"] = _csv(val.strip().strip("[]"))
    elif key == "input":
        val = val.strip().strip("[]")
        for item in _csv(val):
            role, _, t = item.partition(":")
            rec["input"].append({"role": role.strip(), "type": t.strip()})
    elif key == "guard":
        rec["guards"] = [_guard(t) for t in _csvp(val.strip().strip("[]"))]
    else:
        rec["doc"] = val


def _judge_field(name, doc, key, val) -> None:
    rec = next((r for r in doc["judgements"] if r["name"] == name), None)
    if rec is None:
        rec = {"name": name, "model": None, "input": [], "schema": {},
               "doc": ""}
        doc["judgements"].append(rec)
    if key == "model":
        rec["model"] = val.strip()
    elif key == "input":
        val = val.strip().strip("[]")
        for item in _csv(val):
            role, _, t = item.partition(":")
            rec["input"].append({"role": role.strip(), "type": t.strip()})
    elif key == "schema":
        for item in _csv(val):
            field, _, spec = item.partition(":")
            spec = spec.strip()
            if "(" in spec:
                kind_s, _, opts = spec.partition("(")
                opts = opts.rstrip(")")
                rec["schema"][field.strip()] = {
                    "type": kind_s.strip(),
                    "options": [o.strip() for o in opts.split("|") if o.strip()],
                }
            else:
                rec["schema"][field.strip()] = {"type": spec, "options": None}
    else:
        rec["doc"] = val


def _unit_line(doc, val) -> None:
    val = val.strip()
    if "=" in val:
        name, _, expr = val.partition("=")
        name = name.strip()
        if not re.match(r"^[A-Za-z_][\w]*$", name):
            raise ValueError(f"unit name {name!r} is not an identifier")
        fields, scale = derive_unit(name, expr.strip())
        if name in UNIT_TABLE:
            raise ValueError(f"unit {name!r} redefines a built-in token")
        doc["units"][name] = {"dimension": dict(fields), "scale": scale}
        return
    for tok in _csv(val):
        if tok not in UNIT_TABLE:
            raise ValueError(f"unit {tok!r} is not in the unit table")
        fields, scale = UNIT_TABLE[tok]
        doc["units"][tok] = {"dimension": dict(fields), "scale": scale}


def _csv(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


def _unit_of_quantity(text: str) -> str:
    """`value: quantity<m/s>` -> `m/s`."""
    m = re.match(r"^quantity<\s*([^>]+?)\s*>$", text.strip())
    if not m:
        raise ValueError(f"value must be quantity<Unit>: {text!r}")
    return m.group(1)


_GUARD_ARITY = {"exists": 1, "same_owner": 2, "different_owner": 2,
                "frame_eq": 2, "kind": 2, "unit": 2, "framed": 1,
                "positive": 1, "owner_of_type": 2, "frame_of_type": 2}


def _csvp(text: str) -> list[str]:
    """Comma-split at paren/bracket depth 0 (guard args keep inner commas)."""
    out, cur, depth = [], [], 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return [o for o in out if o]


def _guard(text: str) -> dict:
    m = re.match(r"^(\w+)\(([^)]*)\)$", text.strip())
    if not m:
        raise ValueError(f"cannot parse guard {text!r}")
    op, inner = m.groups()
    if op not in _GUARD_ARITY:
        raise ValueError(
            f"guard {op!r} is NOT in the frozen v1 vocabulary "
            f"({sorted(_GUARD_ARITY)}). A new guard kind is a core "
            f"escalation, not a grammar edit.")
    args = _csv(inner)
    if len(args) != _GUARD_ARITY[op]:
        raise ValueError(f"guard {op} takes {_GUARD_ARITY[op]} "
                         f"argument(s), got {len(args)}: {text!r}")
    return {"op": op, "args": args}


def load_domain(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        doc = parse_domain(fh.read())
    return _finalize(doc)


def _finalize(doc: dict) -> dict:
    if not doc:
        return doc
    if "objects" not in doc:
        doc["objects"] = []
    return doc