"""OpenVerifiers — trace store and render views.

One verbose store (the engine's `trace` list) carries everything: derives, rejects,
dead ends, joins, unknowns. The three public views are projections over that single
store — never separate structures (ARCHITECTURE.md §4).

Views:
  * success-path  — the events on a path that reaches the target (or its unknown),
  * failure-trail — success path + rejected/dead-end events,
  * full          — everything, in recorded order.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# view construction
# ---------------------------------------------------------------------------
def build_views(trace: list[dict], target_id: str, answer: Any) -> tuple[list, list, list]:
    """Return (success, failure, full) projected from the single verbose store."""

    full = list(trace)

    # --- success path: derive events that build the answer, traced backwards ---
    # We approximate "the path" as the chain implied by derive events: every derive
    # whose output lies on the dependency closure of the target answer.
    success: list[dict] = []

    def collect_success() -> None:
        # find the derive event(s) that produced target_id (or the answer)
        producers = [e for e in trace if e["type"] == "derive" and e["fact_id"] == target_id
                     and e.get("rule") != "TARGET-REACHED"]
        if not producers:
            producers = [e for e in trace if e["type"] == "derive" and e["fact_id"] == target_id]
        if not producers:
            # target may be a given, or unknown — emit the terminal events only
            for e in trace:
                if e["type"] in ("unknown", "deadend") and ("fact_id" in e and e["fact_id"] == target_id
                                                            or e.get("fact_kind") == _find_target_kind(trace)):
                    success.append(e)
            return
        # walk backwards from the last producer through its inputs
        seen: set[str] = set()
        stack = [producers[-1]]
        by_out: dict[str, list[dict]] = {}
        for e in trace:
            if e["type"] == "derive":
                by_out.setdefault(e["fact_id"], []).append(e)
        while stack:
            e = stack.pop()
            if id(e) in seen:
                continue
            seen.add(id(e))
            success.append(e)
            for parent in e["inputs"]:
                for pe in by_out.get(parent, []):
                    stack.append(pe)
        success.reverse()

    collect_success()

    # --- failure trail: success + rejections + dead ends ---------------------
    failure = list(success)
    for e in trace:
        if e["type"] in ("reject", "deadend", "unknown"):
            failure.append(e)
    # dedupe by id-of-dict
    seen_ids = {id(e) for e in success}
    failure = [e for e in failure if id(e) not in seen_ids or e in success]

    return success, failure, full


def _find_target_kind(trace) -> str:
    for e in trace:
        if e.get("type") == "deadend" and "fact_kind" in e:
            return e["fact_kind"]
    return ""


# ---------------------------------------------------------------------------
# human render
# ---------------------------------------------------------------------------
def render_view(view: str, result) -> str:
    events = {
        "success-path": result.success_path,
        "failure-trail": result.failure_trail,
        "full": result.full,
    }.get(view)
    if events is None:
        raise ValueError(f"unknown view {view!r}; use success-path|failure-trail|full")

    lines: list[str] = []
    lines.append(f"[OpenVerifiers] target={result.target} status={result.status} answer={result.answer}")
    for e in events:
        t = e["type"]
        if t == "derive":
            lines.append(f"  derive {e['fact_id']} = {e['fact_value']}  via {e['rule']}  from {e['inputs']}")
        elif t == "reject":
            lines.append(f"  REJECT {e['rule']} (inputs {e['inputs']}): {e['reason']}")
        elif t == "deadend":
            lines.append(f"  deadend {e.get('fact_kind','?')}: {e['reason']}")
        elif t == "join":
            lines.append(f"  join {e['fact_id']} from {e['sources']}")
        elif t == "unknown":
            lines.append(f"  UNKNOWN {e['fact_id']}: {e['reason']}"
                         + (f" — evidence needed: {e['evidence']}" if e.get("evidence") else ""))
    return "\n".join(lines)