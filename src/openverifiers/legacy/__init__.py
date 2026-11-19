"""OpenVerifiers — SDK surface.

Typed core (Task 0): Dimension/Unit/PhysicalObject/Quantity/ActionFact.
Controllers: EquationController (one equation, every solve direction) and
ConditionController (named predicates, pass/fail/inapplicable).
Engine: runs Transformations; writes the .ovpv audit trace.

No search anywhere: controllers only ever solve/check what was directly asked.
"""

from .units import (Dimension, Unit, Vector3, UnitSystem, to_canonical)
from .objects import PhysicalObject
from .facts import (Fact, Quantity, ActionFact, DerivationRecord,
                    NumericValue, BooleanValue, EnumValue, tag_value,
                    as_number, ForAllFact, ExistsFact, ExpressionFact)
from .errors import (VerifyError, DimensionMismatchError, OwnerMismatchError,
                     SolveError, ConditionFailed, FrameMismatchError,
                     RoleMismatchError)
from .model import Transformation, VerificationResult
from .controllers import (Controller, EquationController, ConditionController,
                          CompositionController, equality_solve)
from .engine import Engine
from .formats import build_audit, save_audit
from .queries import (Premise, Query, FactQuery, ThresholdQuery,
                      ExistenceQuery, ConditionQuery, AggregateQuery,
                      Specifier, Verdict)
from .context import VerifierContext

__all__ = [
    # typed core
    "Dimension", "Unit", "Vector3",
    "UnitSystem", "to_canonical",
    "PhysicalObject",
    "Fact", "Quantity", "ActionFact", "DerivationRecord",
    "NumericValue", "BooleanValue", "EnumValue", "tag_value", "as_number",
    "ForAllFact", "ExistsFact", "ExpressionFact",
    # errors
    "VerifyError", "DimensionMismatchError", "OwnerMismatchError",
    "SolveError", "ConditionFailed", "FrameMismatchError",
    "RoleMismatchError",
    # model / engine / formats
    "Transformation", "VerificationResult", "Engine",
    "build_audit", "save_audit",
    # controllers
    "Controller", "EquationController", "ConditionController",
    "CompositionController", "equality_solve",
    # queries
    "Premise", "Query", "FactQuery", "ThresholdQuery", "ExistenceQuery",
    "ConditionQuery", "AggregateQuery", "Specifier", "Verdict",
    "VerifierContext",
]