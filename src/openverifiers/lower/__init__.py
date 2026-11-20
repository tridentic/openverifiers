"""OV -> RawOV lowering (deterministic, keeps source spans). See docs/LANGUAGE.md."""

from .lower import Lowered, QueryPlan, lower

__all__ = ["Lowered", "QueryPlan", "lower"]
