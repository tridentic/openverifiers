"""Stratification: assign each predicate key a stratum, or explain why not."""

from __future__ import annotations

from ..raw.program import Naf, Pos, Program, effective_body


class NotStratifiable(ValueError):
    """A cycle goes through closed-world negation."""

    def __init__(self, cycle: list[str], rule_id: str) -> None:
        super().__init__(
            f"program is not stratifiable: 'not' in rule {rule_id!r} sits on the "
            f"dependency cycle {' -> '.join(cycle)}")
        self.cycle, self.rule_id = cycle, rule_id


def stratify(program: Program) -> dict[str, int]:
    """Smallest strata with s(head) >= s(pos body) and s(head) > s(closed 'not' body).

    Computed by Bellman-Ford-style relaxation; a stratum above the number of
    predicate keys means a negative cycle, which is reported with its path.
    """
    edges: list[tuple[str, str, int, str]] = []  # body key, head key, weight, rule id
    keys: set[str] = {f.atom.key for f in program.all_facts()}
    for r in program.rules:
        keys.add(r.head.key)
        for lit in effective_body(r, program):
            if isinstance(lit, Pos | Naf):
                keys.add(lit.atom.key)
                edges.append((lit.atom.key, r.head.key, int(isinstance(lit, Naf)), r.id))
    strata = dict.fromkeys(keys, 0)
    limit = len(keys)
    changed = True
    while changed:
        changed = False
        for src, dst, w, _ in edges:
            if strata[src] + w > strata[dst]:
                strata[dst] = strata[src] + w
                changed = True
                if strata[dst] > limit:
                    raise NotStratifiable(*_negative_cycle(edges, dst))
    return strata


def _negative_cycle(edges: list[tuple[str, str, int, str]], start: str) -> tuple[list[str], str]:
    """A cycle containing a negative edge: path ``dst -> ... -> src -> dst``, and its rule."""
    succ: dict[str, list[str]] = {}
    for src, dst, _, _ in edges:
        succ.setdefault(src, []).append(dst)
    for src, dst, w, rid in edges:
        if w != 1:
            continue
        parent: dict[str, str | None] = {dst: None}
        queue = [dst]
        while queue:
            node = queue.pop(0)
            if node == src:
                path = [src]
                while (prev := parent[path[-1]]) is not None:
                    path.append(prev)
                return [*reversed(path), dst], rid
            for nxt in succ.get(node, []):
                if nxt not in parent:
                    parent[nxt] = node
                    queue.append(nxt)
    return [start], ""
