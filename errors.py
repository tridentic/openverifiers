"""OpenVerifiers — typed verification errors.

Distinct failure classes so callers (and tests) can assert on the *reason* a
verification failed, not just that it failed. `reason` strings keep the same
vocabulary the untyped engine used ("dimension mismatch", "owner mismatch",
"unit/dimension mismatch", ...).
"""


class VerifyError(Exception):
    """Base class for all verification failures."""


class DimensionMismatchError(VerifyError):
    """A fact's dimension does not match the role its rule expects."""


class OwnerMismatchError(VerifyError):
    """A rule requiring a shared physical context received facts owned by
    different objects."""


class SolveError(VerifyError):
    """The declared equation could not be solved for the declared target."""


class ConditionFailed(VerifyError):
    """A ConditionController condition produced a hard failure verdict."""


class FrameMismatchError(VerifyError):
    """Frame-bearing facts from different reference frames met in one rule."""


class RoleMismatchError(VerifyError):
    """A typed role (e.g. Velocity) received a fact of a different role type,
    checked before dimensions — role-typing, not just dimension-matching."""